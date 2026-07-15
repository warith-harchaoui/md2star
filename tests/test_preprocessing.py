"""
test_preprocessing.py — Unit tests for md2star.preprocessing.

Tests for the ``preprocess_markdown`` function, which runs the full
preprocessor pipeline (list spacing, HTML→pipe-table conversion, mermaid
rendering, math unwrapping, image normalization, PPTX slide isolation, …).

A shared ``conftest.py`` fixture redirects the on-disk cache to a fresh
``tmp_path`` for every test, so SVG/raster artifacts land in a known
location and do not pollute the user's real ``$XDG_CACHE_HOME/md2star/``.

Design note (rule 13 — "rationalize at the 100-test mark"): value-varying
micro-tests are folded into ``@pytest.mark.parametrize`` cases so every
(input, expected) pair remains a distinct, named case while the function
count stays small. Genuinely distinct behaviours and regression pins stay
as their own functions.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import patch

import pytest

from md2star.cache import cache_dir
from md2star.preprocessing import preprocess_markdown


def _module_importable(name: str) -> bool:
    """True iff ``import name`` would succeed in this venv."""
    import importlib.util

    return importlib.util.find_spec(name) is not None


def _pp(text: str, **kwargs) -> str:
    """Run ``preprocess_markdown`` with the test-default flags.

    Almost every test disables metadata injection and linting so it can
    assert on the structural transform alone. This helper centralizes
    those defaults; callers override via ``**kwargs`` when they need the
    language/metadata passes on.

    Parameters
    ----------
    text : str
        Markdown source to preprocess.
    **kwargs
        Forwarded to ``preprocess_markdown``; overrides the defaults.

    Returns
    -------
    str
        The preprocessed markdown.
    """
    # Default the two flags most tests turn off, but let callers win.
    kwargs.setdefault("inject_metadata", False)
    kwargs.setdefault("lint_enabled", False)
    return preprocess_markdown(text, **kwargs)


def _separator_cells(result: str) -> list[str]:
    """Return the cells of a pipe-table separator row (``|:--|--:|``).

    Parameters
    ----------
    result : str
        Preprocessed markdown containing exactly one pipe-table.

    Returns
    -------
    list[str]
        Per-column separator cell strings, outer pipes stripped.
    """
    # A separator row is the only ``|``-line made purely of ``|-: `` chars.
    sep_line = next(
        ln for ln in result.split("\n")
        if ln.startswith("|") and set(ln) <= set("|-: ")
    )
    return sep_line.strip("|").split("|")


# ──────────────────────────────────────────────────────────────────
# Basic / edge-case pass-through
# ──────────────────────────────────────────────────────────────────


# Inputs that must survive the pipeline byte-for-byte. Each guards a
# different "no transformation should fire" edge case.
@pytest.mark.parametrize(
    "text",
    [
        pytest.param("", id="empty-string"),
        pytest.param("Hello\nworld\n\nParagraph two.", id="prose-no-lists"),
        pytest.param("\n\n\n", id="blank-lines-only"),
        pytest.param("Hello\n\n- item", id="already-spaced-list"),
    ],
)
def test_passthrough_unchanged(text: str) -> None:
    """Inputs with nothing to transform pass through byte-for-byte."""
    assert _pp(text) == text


# ──────────────────────────────────────────────────────────────────
# List spacing (unordered, ordered, nested)
# ──────────────────────────────────────────────────────────────────


# One case per list flavour: a blank line must be injected between the
# preceding block and each list item so Pandoc treats it as a loose list.
@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param("Hello\n- item", "Hello\n\n- item", id="dash-marker"),
        pytest.param("Hello\n* item", "Hello\n\n* item", id="star-marker"),
        pytest.param("Hello\n+ item", "Hello\n\n+ item", id="plus-marker"),
        pytest.param(
            "- a\n- b\n- c", "- a\n\n- b\n\n- c", id="consecutive-items"
        ),
        pytest.param(
            "Intro\n1. First\n2. Second",
            "Intro\n\n1. First\n\n2. Second",
            id="ordered-single-digit",
        ),
        # Regex must handle numbers > 9, not just 1-9.
        pytest.param("Intro\n10. Tenth", "Intro\n\n10. Tenth", id="ordered-multi-digit"),
        # Indented sub-items keep their indent while still getting spacing.
        pytest.param(
            "- parent\n  - child", "- parent\n\n  - child", id="nested-item"
        ),
        # Headings are treated like paragraphs: they need spacing before a list.
        pytest.param(
            "## Heading\n- item", "## Heading\n\n- item", id="heading-then-list"
        ),
        # Paragraph → list → paragraph: spacing goes in front of the list only.
        pytest.param(
            "Intro\n- a\n- b\nOutro",
            "Intro\n\n- a\n\n- b\nOutro",
            id="paragraph-list-paragraph",
        ),
    ],
)
def test_blank_line_inserted_before_lists(text: str, expected: str) -> None:
    """Text preceding a list item gets a blank line inserted (all marker kinds)."""
    assert _pp(text) == expected


# ──────────────────────────────────────────────────────────────────
# Code-block preservation
# ──────────────────────────────────────────────────────────────────


def test_code_block_list_syntax_preserved() -> None:
    """Lines inside ``` … ``` must not trigger blank-line injection."""
    # Critical: code examples often contain list-like syntax to leave alone.
    text = "```\n- not a list\n```"
    assert _pp(text) == text


def test_code_block_with_surrounding_real_list() -> None:
    """A fenced list-like block is left alone; a real list after it gets spacing."""
    # Mixed content: fence contains list-like syntax, then a genuine list.
    text = "Before\n```\n- code\n```\nAfter\n- real list"
    result = _pp(text)
    # The "- code" inside the fence stays untouched (code preservation).
    assert "```\n- code\n```" in result
    # The real list item after the fence gets its blank line (list formatting).
    assert "After\n\n- real list" in result


# ──────────────────────────────────────────────────────────────────
# Bibliography & citation preservation
# ──────────────────────────────────────────────────────────────────


# Pandoc ``@key`` / ``[@key]`` citations must survive verbatim, whether they
# sit inside a list (which does get spacing) or in flowing prose (untouched).
@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param(
            "Related works:\n- [@pearl2000]\n- See @smith2019 for details",
            "Related works:\n\n- [@pearl2000]\n\n- See @smith2019 for details",
            id="citations-in-list",
        ),
        pytest.param(
            "As proven by @einstein1905, this works.\n\nMore info [@turing1936].",
            "As proven by @einstein1905, this works.\n\nMore info [@turing1936].",
            id="inline-citations",
        ),
    ],
)
def test_citations_preserved(text: str, expected: str) -> None:
    """Pandoc bibliography citations survive intact (list spacing aside)."""
    assert _pp(text) == expected


# ──────────────────────────────────────────────────────────────────
# Mermaid block rendering
# ──────────────────────────────────────────────────────────────────


class TestMermaidBlocks:
    """Tests evaluating the local Mermaid rendering pipeline."""

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    def test_mermaid_renders_success(self, mock_fetch) -> None:
        """A valid mermaid block is substituted with the rendered PNG absolute path."""
        mock_fetch.return_value = "/absolute/dummy.png"
        text = "Intro\n```mermaid\ngraph TD;\n    A-->B\n```\nOutro"
        result = _pp(text)
        assert "![](/absolute/dummy.png)" in result
        assert "```mermaid" not in result

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    def test_mermaid_renders_fallback(self, mock_fetch) -> None:
        """A failed mermaid render falls back gracefully without modifying source."""
        mock_fetch.side_effect = Exception("Test Mermaid Error")
        text = "Intro\n```mermaid\ngraph TD;\n    A-->B\n```\nOutro"
        result = _pp(text)
        assert "```mermaid\ngraph TD;\n    A-->B\n```" in result
        assert "![](" not in result

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    @pytest.mark.parametrize(
        "size, expected_attr",
        [
            # A wider-than-tall PNG caps width (height auto).
            pytest.param((3000, 1000), "{width=15cm}", id="wide-caps-width"),
            # A taller-than-wide PNG caps height (width auto).
            pytest.param((600, 2500), "{height=17cm}", id="tall-caps-height"),
        ],
    )
    def test_mermaid_aspect_ratio_cap(
        self, mock_fetch, tmp_path, size, expected_attr
    ) -> None:
        """A rendered mermaid PNG gets an A4 cap chosen by its aspect ratio."""
        from PIL import Image

        png = tmp_path / "diagram.png"
        Image.new("RGB", size, "white").save(png)
        mock_fetch.return_value = str(png)
        result = _pp("```mermaid\ngraph LR;\nA-->B\n```")
        assert f"![]({png}){expected_attr}" in result

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    def test_mermaid_unreadable_png_falls_back_to_width100(self, mock_fetch) -> None:
        """If Pillow cannot open the render, the ``{width=100%}`` fallback still applies."""
        mock_fetch.return_value = "/absolute/dummy.png"
        result = _pp("```mermaid\ngraph TD;\nA-->B\n```")
        assert "![](/absolute/dummy.png){width=100%}" in result


# ──────────────────────────────────────────────────────────────────
# A4-fitting image cap (applies to ALL bare images, not just mermaid)
# ──────────────────────────────────────────────────────────────────


class TestA4ImageCap:
    """Bare ``![](src)`` images are capped to A4 dimensions by aspect ratio."""

    @pytest.mark.parametrize(
        "size, expected_attr",
        [
            # Longest side ≤ 1600 px so process_image_assets leaves the path alone.
            pytest.param((1500, 500), "{width=15cm}", id="wide-caps-width"),
            pytest.param((500, 1500), "{height=17cm}", id="tall-caps-height"),
        ],
    )
    def test_local_image_aspect_ratio_cap(self, tmp_path, size, expected_attr) -> None:
        """A measurable local image gets an A4 cap chosen by aspect ratio."""
        from PIL import Image

        png = tmp_path / "img.png"
        Image.new("RGB", size, "white").save(png)
        result = _pp(f"Photo:\n\n![]({png})\n")
        assert f"![]({png}){expected_attr}" in result

    def test_remote_url_falls_back_to_width100(self) -> None:
        """URLs cannot be measured offline — fall back to the generic 100% width."""
        result = _pp("![](https://example.invalid/cannot-fetch.png)\n")
        assert "https://example.invalid/cannot-fetch.png){width=100%}" in result

    def test_existing_attrs_are_preserved(self) -> None:
        """Images that already declare ``{…}`` are left untouched."""
        result = _pp("![](/path/to/img.png){width=5cm}\n")
        assert "![](/path/to/img.png){width=5cm}" in result
        assert "{width=15cm}" not in result
        assert "{height=17cm}" not in result


# ──────────────────────────────────────────────────────────────────
# HTML table conversion
# ──────────────────────────────────────────────────────────────────


class TestHtmlTables:
    """Tests that HTML <table> blocks are converted to Markdown pipe-tables."""

    def test_simple_table(self) -> None:
        """A basic two-column HTML table should become a Markdown pipe-table."""
        html = (
            "<table><tr><th>Name</th><th>Value</th></tr>"
            "<tr><td>Alice</td><td>42</td></tr></table>"
        )
        result = _pp(html)
        assert "| Name" in result
        assert "| Alice" in result
        assert "<table>" not in result

    def test_inline_html_in_cells(self) -> None:
        """<code>, <strong> and <em> inside cells must become Markdown markers."""
        html = (
            "<table>"
            "<tr><th>Start</th><th>Role</th><th>Text</th></tr>"
            "<tr><td><code>3 sec</code></td><td><strong>Operator</strong></td><td>Hello</td></tr>"
            "</table>"
        )
        result = _pp(html)
        assert "`3 sec`" in result
        assert "**Operator**" in result
        assert "<code>" not in result
        assert "<strong>" not in result

    def test_multirow_table(self) -> None:
        """Multiple data rows should all appear in the output."""
        html = (
            "<table>"
            "<tr><th>A</th><th>B</th></tr>"
            "<tr><td>1</td><td>2</td></tr>"
            "<tr><td>3</td><td>4</td></tr>"
            "</table>"
        )
        result = _pp(html)
        assert "| 1" in result
        assert "| 3" in result

    def test_table_separator_row(self) -> None:
        """Output must contain a separator line (---)."""
        html = "<table><tr><th>Col</th></tr><tr><td>data</td></tr></table>"
        result = _pp(html)
        assert "|---" in result or "|--" in result

    def test_non_table_html_untouched(self) -> None:
        """Non-table HTML (e.g. <div>) should pass through unmodified."""
        result = _pp("<div>Hello</div>")
        assert "<div>Hello</div>" in result


# ──────────────────────────────────────────────────────────────────
# Pipe-table separator normalization + cell wrapping
# ──────────────────────────────────────────────────────────────────


class TestPipeTableNormalization:
    """Tests that pipe-table separators get proportional dashes + trailing blank line."""

    def test_uniform_separator_rewritten_proportionally(self) -> None:
        """A 4 / 141 / 7-character row should produce a wide middle separator cell."""
        long_desc = "A" * 140
        text = (
            "| ID | Description | Section |\n"
            "|---|---|---|\n"
            f"| C1 | {long_desc} | §6 |\n"
        )
        cells = _separator_cells(_pp(text))
        assert len(cells) == 3
        # Middle cell must be the widest, by a lot.
        assert len(cells[1]) > len(cells[0]) * 5
        assert len(cells[1]) > len(cells[2]) * 5
        # Total dashes must exceed Pandoc's --columns default (72) so widths take effect.
        assert sum(len(c) for c in cells) > 72

    def test_blank_line_after_table(self) -> None:
        """A paragraph glued to a table must be split off by a blank line."""
        text = "| A | B |\n|---|---|\n| 1 | 2 |\nNext paragraph."
        result = _pp(text)
        assert "| 1 | 2 |\n\nNext paragraph." in result

    def test_alignment_markers_preserved(self) -> None:
        """``:---:`` / ``---:`` / ``:---`` alignment markers must survive rewriting."""
        text = "| L | C | R |\n|:---|:---:|---:|\n| 1 | 2 | 3 |\n"
        cells = _separator_cells(_pp(text))
        assert cells[0].startswith(":") and not cells[0].endswith(":")
        assert cells[1].startswith(":") and cells[1].endswith(":")
        assert cells[2].endswith(":") and not cells[2].startswith(":")

    def test_idempotent(self) -> None:
        """Running preprocessing twice should produce the same output."""
        text = "| A | B |\n|---|---|\n| 1 | 2 |\n\nAfter."
        once = _pp(text)
        twice = _pp(once)
        assert once == twice

    def test_table_in_code_block_untouched(self) -> None:
        """A pipe-table-looking block inside a fenced code block must not be rewritten."""
        text = "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```\n"
        result = _pp(text)
        assert "|---|---|" in result

    def test_long_path_gets_soft_breaks(self) -> None:
        """Long unbreakable strings in a cell get zero-width spaces after / and _."""
        # File-path-shaped content longer than the 25-char threshold should be
        # made wrappable so narrow columns don't fall back to char-per-line.
        text = (
            "| Path | Notes |\n"
            "|---|---|\n"
            "| data/conversations/long_record_id.json | one per conversation |\n"
        )
        result = _pp(text)
        # Zero-width space (U+200B) should appear after slashes and underscores
        # inside the long path string.
        assert "/​" in result
        assert "_​" in result
        # Short content untouched.
        assert "one per conversation" in result
        # The visible string still reads as the original path (ZWSP is invisible).
        assert "data/conversations/long_record_id.json" in result.replace("​", "")

    def test_short_cell_no_soft_breaks(self) -> None:
        """Cells without long unbreakable runs are not modified."""
        text = "| A | B |\n|---|---|\n| short | also short |\n"
        assert "​" not in _pp(text)

    def test_long_cell_gets_br_breaks(self) -> None:
        """A >120 char cell is broken at sentence boundaries with ``<br/>``."""
        long_cell = (
            "This is the first sentence in the long cell. "
            "This is the second sentence in the long cell. "
            "This is the third sentence so the total exceeds the wrap threshold."
        )
        text = f"| A | B |\n|---|---|\n| short | {long_cell} |\n"
        result = _pp(text)
        assert "<br/>" in result
        # All visible content preserved (modulo whitespace shuffling).
        for fragment in ("first sentence", "second sentence", "third sentence"):
            assert fragment in result

    def test_short_cell_not_wrapped(self) -> None:
        """A short cell must not get any ``<br/>`` inserted."""
        text = "| A | B |\n|---|---|\n| short | a brief explanation |\n"
        assert "<br" not in _pp(text)

    def test_code_span_in_cell_preserved(self) -> None:
        """Backtick code spans inside a cell are left exactly as-written."""
        # The soft-break pass must skip code spans so identifiers inside backticks
        # still render as a single ``<w:t>`` run with no injected characters.
        text = (
            "| Variant | Code |\n"
            "|---|---|\n"
            "| heuristic | `ROITELET_ROUTER_long_constant_name_here` |\n"
        )
        result = _pp(text)
        assert "`ROITELET_ROUTER_long_constant_name_here`" in result

    def test_math_in_cell_preserved_from_soft_breaks(self) -> None:
        """Math formulas in a cell must not get ZWSPs sprinkled into subscripts."""
        # A ZWSP between ``_`` and the subscript content would break LaTeX
        # rendering of ``\alpha_{long_subscript_name}``.
        text = (
            "| Symbol | Meaning |\n"
            "|---|---|\n"
            "| $\\alpha_{long_subscript_name_here}$ | a long subscripted variable |\n"
        )
        result = _pp(text)
        # Zero-width space (U+200B) must NOT appear inside the math chunk.
        assert "$\\alpha_{long_subscript_name_here}$" in result
        assert "​" not in result.split("$")[1]


# ──────────────────────────────────────────────────────────────────
# Image width auto-injection (bare markdown images)
# ──────────────────────────────────────────────────────────────────


# ``process_image_assets`` cannot measure these (no local file), so they take
# the generic ``{width=100%}`` path — unless an explicit width is present.
@pytest.mark.parametrize(
    "text, present, absent",
    [
        pytest.param(
            "![alt](/abs/path/to/image.png)",
            "![alt](/abs/path/to/image.png){width=100%}",
            None,
            id="bare-image-gets-width",
        ),
        pytest.param(
            "![alt](/abs/path/to/image.png){width=50%}",
            "{width=50%}",
            "{width=100%}",
            id="existing-width-not-double-decorated",
        ),
        pytest.param(
            "![](https://example.com/img.jpg)",
            "{width=100%}",
            None,
            id="empty-alt-remote-gets-width",
        ),
    ],
)
def test_bare_image_width_injection(text: str, present: str, absent: str | None) -> None:
    """Bare image links get ``{width=100%}`` unless they already declare a width."""
    result = _pp(text)
    assert present in result
    if absent is not None:
        assert absent not in result


# ──────────────────────────────────────────────────────────────────
# Image path absolutization
# ──────────────────────────────────────────────────────────────────


class TestImagePathAbsolutization:
    """Relative image paths must be rewritten to absolute against ``base_dir``."""

    def test_relative_path_becomes_absolute(self, tmp_path) -> None:
        """A plain relative path is joined onto base_dir."""
        result = _pp("![](images/foo.png)", base_dir=str(tmp_path))
        assert f"![]({tmp_path}/images/foo.png)" in result

    def test_parent_relative_path_resolves(self, tmp_path) -> None:
        """``../`` segments must be normalized, not left literal."""
        sub = tmp_path / "sub"
        sub.mkdir()
        result = _pp("![](../foo.png)", base_dir=str(sub))
        assert f"![]({tmp_path}/foo.png)" in result

    # Paths/URIs that must NOT be re-rooted under base_dir. Each guards a
    # different "already resolvable / not a local path" class of ref.
    @pytest.mark.parametrize(
        "text, present, joined_prefix",
        [
            pytest.param(
                "![](/already/absolute.png)",
                "![](/already/absolute.png)",
                "/already",
                id="absolute-path",
            ),
            pytest.param(
                "![](https://nonexistent.invalid.tld/img.png)",
                "https://nonexistent.invalid.tld/img.png",
                "https:",
                id="http-url",
            ),
            pytest.param(
                "![](data:image/png;base64,iVBORw0KGgo=)",
                "data:image/png;base64,iVBORw0KGgo=",
                "data:",
                id="data-uri",
            ),
        ],
    )
    def test_non_relative_refs_not_rerooted(
        self, tmp_path, text, present, joined_prefix
    ) -> None:
        """Absolute paths, HTTP URLs, and data URIs are never joined with base_dir."""
        result = _pp(text, base_dir=str(tmp_path))
        assert present in result
        # The base_dir must not have been prepended onto the untouched ref.
        assert f"{tmp_path}/{joined_prefix}" not in result

    def test_code_block_paths_untouched(self, tmp_path) -> None:
        """Image syntax inside fenced code blocks is example text, not a real ref."""
        result = _pp("```\n![](relative/in/code.png)\n```", base_dir=str(tmp_path))
        assert "![](relative/in/code.png)" in result
        assert f"{tmp_path}/relative/in/code.png" not in result

    def test_multiple_images_same_line(self, tmp_path) -> None:
        """Every image on a single line is absolutized independently."""
        result = _pp("![a](one.png) ![b](sub/two.png)", base_dir=str(tmp_path))
        assert f"![a]({tmp_path}/one.png)" in result
        assert f"![b]({tmp_path}/sub/two.png)" in result

    def test_linked_image(self, tmp_path) -> None:
        """The image inside ``[![](img)](url)`` must still be absolutized."""
        result = _pp("[![](thumb.png)](https://example.com)", base_dir=str(tmp_path))
        assert f"![]({tmp_path}/thumb.png)" in result
        assert "https://example.com" in result

    def test_pipe_table_cell_image_absolutized(self, tmp_path) -> None:
        """Images inside table cells must also resolve against base_dir.

        ``normalize_pipe_tables`` sprinkles zero-width spaces into table
        contents for soft-wrapping, so we strip them before checking.
        """
        text = "| col |\n|-----|\n| ![](cell.png) |\n"
        result = _pp(text, base_dir=str(tmp_path)).replace("​", "")
        assert "(cell.png)" not in result
        assert str(tmp_path) in result


# ──────────────────────────────────────────────────────────────────
# SVG → PNG conversion + raster downscaling
# ──────────────────────────────────────────────────────────────────


class TestImageAssetProcessing:
    """SVGs become PNGs; oversized rasters get a downscaled sibling.

    Output artifacts now live in the XDG cache (redirected to ``tmp_path``
    by the conftest fixture), keyed by source-path MD5 — so we look in
    ``cache_dir("resized") / "<hash>_max<N>.<ext>"`` rather than next to
    the source file.
    """

    @staticmethod
    def _has_rsvg() -> bool:
        import shutil as _shutil

        return _shutil.which("rsvg-convert") is not None

    def _make_svg(self, tmp_path, name: str = "logo.svg") -> Path:
        svg = tmp_path / name
        svg.write_text(
            '<?xml version="1.0"?>'
            '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
            '<rect width="100" height="100" fill="red"/></svg>'
        )
        return svg

    @pytest.mark.skipif(
        not (__import__("shutil").which("rsvg-convert")
             or _module_importable("cairosvg")),
        reason="needs librsvg (rsvg-convert) or cairosvg installed",
    )
    def test_svg_rewritten_to_png(self, tmp_path) -> None:
        """A markdown-image SVG is rendered to a cached PNG and the ref rewritten."""
        svg = self._make_svg(tmp_path)
        result = _pp(f"![logo]({svg.name})", base_dir=str(tmp_path))
        # Cached PNGs land in cache_dir("resized") with a hash-based name.
        cached_pngs = list(cache_dir("resized").glob("*_max*.png"))
        assert cached_pngs, "expected the SVG to be rendered into the cache dir"
        assert any(str(p) in result for p in cached_pngs)
        assert "logo.svg" not in result

    @pytest.mark.skipif(
        not (__import__("shutil").which("rsvg-convert")
             or _module_importable("cairosvg")),
        reason="needs librsvg (rsvg-convert) or cairosvg installed",
    )
    def test_svg_inside_html_img_also_rewritten(self, tmp_path) -> None:
        """An SVG referenced from a raw ``<img src>`` is rewritten too."""
        svg = self._make_svg(tmp_path, "diagram.svg")
        text = f'<img src="{svg.name}" alt="diagram" width="100%">'
        result = _pp(text, base_dir=str(tmp_path))
        assert "diagram.svg" not in result
        # PNG lands in the cache, not next to the source.
        cached_pngs = list(cache_dir("resized").glob("*_max*.png"))
        assert any(str(p) in result for p in cached_pngs)

    def test_oversized_raster_downscaled(self, tmp_path) -> None:
        """A >1600px raster gets a downscaled cached sibling, aspect preserved."""
        from PIL import Image as PILImage

        big = tmp_path / "big.png"
        PILImage.new("RGB", (3200, 1600), color=(0, 128, 255)).save(big)
        result = _pp(f"![]({big.name})", base_dir=str(tmp_path))
        cached = list(cache_dir("resized").glob("*_max1600.png"))
        assert cached, "expected a downscaled copy in the resized cache"
        with PILImage.open(cached[0]) as resized:
            w, h = resized.size
        assert max(w, h) == 1600
        # 3200/1600 = 2× downscale, so the shorter side should land at 800.
        assert min(w, h) == 800
        assert str(cached[0]) in result

    def test_small_raster_passes_through(self, tmp_path) -> None:
        """An under-threshold raster is left in place with nothing cached."""
        from PIL import Image as PILImage

        small = tmp_path / "small.png"
        PILImage.new("RGB", (400, 300), color=(255, 0, 0)).save(small)
        result = _pp(f"![]({small.name})", base_dir=str(tmp_path))
        assert str(small) in result
        # Nothing should have landed in the cache for an under-threshold image.
        assert not list(cache_dir("resized").glob("*"))

    def test_url_image_untouched(self, tmp_path) -> None:
        """The asset processor must not try to download / convert URLs."""
        result = _pp("![](https://example.invalid/img.svg)", base_dir=str(tmp_path))
        assert "https://example.invalid/img.svg" in result

    def test_html_p_wrapped_img_flattened_to_markdown(self, tmp_path) -> None:
        """``<p align="center"><img …></p>`` survives Pandoc DOCX by being
        rewritten as a Markdown image (the surrounding raw-HTML block
        would otherwise be dropped by the DOCX writer)."""
        from PIL import Image as PILImage

        img = tmp_path / "hero.png"
        PILImage.new("RGB", (200, 100), color=(0, 0, 0)).save(img)
        text = (
            '<p align="center">\n'
            f'  <img src="{img.name}" alt="hero shot" width="100%">\n'
            '</p>\n'
        )
        result = _pp(text, base_dir=str(tmp_path))
        assert "<p" not in result and "<img" not in result
        assert f"![hero shot]({img})" in result
        assert "{width=100%}" in result

    def test_html_img_inside_fenced_code_preserved(self, tmp_path) -> None:
        """``<img>`` shown inside a code fence is example text, not a real ref."""
        text = "```\n<img src=\"shown-as-code.png\">\n```"
        result = _pp(text, base_dir=str(tmp_path))
        assert '<img src="shown-as-code.png">' in result


# ──────────────────────────────────────────────────────────────────
# Pipe-table column-width slack for single-word columns
# ──────────────────────────────────────────────────────────────────


class TestSingleWordColumnSlack:
    """Single-word columns get extra width because they can't wrap."""

    @staticmethod
    def _separator_dashes(table_md: str) -> list[int]:
        """Return the dash-count of each column in the separator row.

        Parameters
        ----------
        table_md : str
            Raw markdown table to preprocess.

        Returns
        -------
        list[int]
            Per-column count of ``-`` characters in the separator row.
        """
        result = _pp(table_md)
        sep_line = next(
            ln for ln in result.split("\n") if re.match(r"^\|[-:|]+\|$", ln.strip())
        )
        # Drop outer pipes, split on inner pipes, count only dash characters
        # (alignment colons don't add visual width).
        inner = sep_line.strip()[1:-1]
        return [cell.count("-") for cell in inner.split("|")]

    def test_single_word_column_wider_than_multi_word_peer(self) -> None:
        """A column of single words should claim more dashes than a multi-word
        column whose cells share the same character length."""
        # Both columns have cells exactly 8 characters long. Column A is
        # unbreakable (single word); column B has a space at position 4.
        single = (
            "| A        | B        |\n"
            "|---|---|\n"
            "| abcdefgh | ab cdefg |\n"
            "| ijklmnop | ij klmno |\n"
            "| qrstuvwx | qr stuvw |\n"
        )
        dashes = self._separator_dashes(single)
        assert len(dashes) == 2
        assert dashes[0] > dashes[1], (
            f"single-word column A should get more dashes than multi-word B, "
            f"got {dashes}"
        )

    def test_all_multi_word_columns_get_no_slack(self) -> None:
        """When every column has multi-word cells, neither gets the slack."""
        multi = (
            "| A      | B      |\n"
            "|---|---|\n"
            "| a a b  | b b c  |\n"
            "| c c d  | d d e  |\n"
        )
        dashes = self._separator_dashes(multi)
        assert len(dashes) == 2
        # Columns have identical longest-line length and identical wrap
        # potential, so the dash counts should match.
        assert dashes[0] == dashes[1], f"expected equal widths, got {dashes}"

    def test_idempotent(self) -> None:
        """Running the normalization twice produces identical output, so the
        single-word slack doesn't compound on repeated runs."""
        table = (
            "| A        | B        |\n"
            "|---|---|\n"
            "| abcdefgh | ab cdefg |\n"
            "| ijklmnop | ij klmno |\n"
        )
        once = _pp(table)
        twice = _pp(once)
        assert once == twice, "single-word slack must not compound across runs"


# ──────────────────────────────────────────────────────────────────
# PPTX slide isolation
# ──────────────────────────────────────────────────────────────────


class TestPptxSlideIsolation:
    """Tables and images on a populated slide should be split onto fresh slides."""

    @staticmethod
    def _marker_between(result: str, start_pred, end_pred) -> bool:
        """True iff a bare ``##`` slide marker sits between two matched lines.

        Parameters
        ----------
        result : str
            Preprocessed markdown to scan.
        start_pred, end_pred : Callable[[str], bool]
            Predicates picking the first line of the opening/closing anchor.

        Returns
        -------
        bool
            Whether any line strictly between the anchors is a lone ``##``.
        """
        lines = result.split("\n")
        start = next(i for i, ln in enumerate(lines) if start_pred(ln))
        end = next(i for i, ln in enumerate(lines) if end_pred(ln))
        return any(ln.strip() == "##" for ln in lines[start + 1 : end])

    def test_table_after_prose_gets_own_slide(self) -> None:
        """A pipe-table that follows prose gets a synthetic blank ``##`` inserted."""
        text = (
            "## Section\n\n"
            "Some intro prose.\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        result = _pp(text)
        # A new blank ``##`` slide marker must appear between the prose and the
        # table so Pandoc renders the table on its own PPTX slide.
        assert self._marker_between(
            result, lambda ln: "intro prose" in ln, lambda ln: ln.startswith("| A")
        )

    def test_two_tables_in_one_section_each_get_own_slide(self) -> None:
        """A second table in the same section is split off onto a new slide."""
        text = (
            "## Section\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "| C | D |\n|---|---|\n| 3 | 4 |\n"
        )
        result = _pp(text)
        assert self._marker_between(
            result, lambda ln: ln.startswith("| A"), lambda ln: ln.startswith("| C")
        )

    def test_first_table_in_section_not_isolated(self) -> None:
        """A table that opens a section directly is left where it is."""
        text = "## Section\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        result = _pp(text)
        # No bare ``##`` slide marker should appear between the heading and the
        # table because the section starts with the table.
        assert not self._marker_between(
            result, lambda ln: ln.startswith("## "), lambda ln: ln.startswith("| A")
        )

    def test_pipe_table_inside_code_block_not_treated_as_table(self) -> None:
        """A pipe-table-shaped block inside a fenced code block does not trigger isolation."""
        text = (
            "## Section\n\n"
            "Some prose.\n\n"
            "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```\n"
        )
        result = _pp(text)
        # The code-fenced ``| A | B |`` must NOT trigger a slide split.
        # We assert by checking that no bare ``##`` was inserted before the fence.
        lines = result.split("\n")
        fence_idx = next(i for i, ln in enumerate(lines) if ln.strip() == "```")
        assert not any(ln.strip() == "##" for ln in lines[:fence_idx])

    def test_isolation_is_idempotent(self) -> None:
        """Re-running the pipeline must not stack extra blank ``##`` separators.

        Regression guard: the slide-isolation walker used to match only
        ``"## "`` (with a trailing space), so it did not recognize the
        *empty* ``##`` separator it had itself emitted. A table already
        preceded by that separator then got a second one on every re-run,
        so ``preprocess_markdown`` was not a fixed point — the property the
        md ↔ docx round-trip guarantee (see tests/test_roundtrip.py) rests
        on. Two passes must now yield identical output.
        """
        text = (
            "## Section\n\n"
            "Some intro prose.\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        once = _pp(text)
        twice = _pp(once)
        assert once == twice
        # And exactly one blank separator was inserted, not a growing pile.
        assert once.count("\n##\n") + once.count("\n## \n") <= 1


# ──────────────────────────────────────────────────────────────────
# Math-in-code unwrapping
# ──────────────────────────────────────────────────────────────────


class TestMathInCodeSpans:
    """Backticks wrapping LaTeX math should be rewritten into proper math.

    Pandoc renders backtick content verbatim, so ``\\`$x^2$\\``` would
    otherwise come out as a monospaced ``$x^2$`` literal instead of as
    rendered math. The preprocessor unwraps pure-math spans and merges
    mixed text/math spans into a single math expression.
    """

    # Each delimiter form (``$..$``, ``$$..$$``, ``\(..\)``, ``\[..\]``) is a
    # distinct recognizer branch; a pure-math code span unwraps to bare math.
    @pytest.mark.parametrize(
        "src, expected",
        [
            pytest.param("`$x^2$`", "$x^2$", id="inline-dollar"),
            pytest.param("`$$x^2$$`", "$$x^2$$", id="display-dollar"),
            pytest.param(r"`\(x^2\)`", r"\(x^2\)", id="inline-paren"),
            pytest.param(r"`\[x^2\]`", r"\[x^2\]", id="display-bracket"),
        ],
    )
    def test_pure_math_unwrapped(self, src: str, expected: str) -> None:
        """A code span whose content is exactly one math chunk unwraps to bare math."""
        assert _pp(src) == expected

    # Mixed text+math spans collapse into a single ``$..$`` with prose wrapped
    # in ``\text{}``; each case pins a different interleaving of text and math.
    @pytest.mark.parametrize(
        "src, expected",
        [
            # Headline case: snake_case prose reads as words, underscore would
            # otherwise be parsed as a math subscript.
            pytest.param(
                "sharing one `quality_threshold $\\in [0,1]$` knob",
                "sharing one $\\text{quality threshold} \\in [0,1]$ knob",
                id="snake-case-identifier",
            ),
            # Text *after* the math chunk is wrapped in \text{}.
            pytest.param(
                "`$x^2$ when x is real`",
                "$x^2 \\text{when x is real}$",
                id="text-after-math",
            ),
            # Multiple math chunks interleaved with text merge into one expr.
            pytest.param(
                "`if $a$ then $b$`",
                "$\\text{if} a \\text{then} b$",
                id="multiple-math-chunks",
            ),
        ],
    )
    def test_mixed_text_math_merged(self, src: str, expected: str) -> None:
        """Mixed text/math code spans collapse to one math expression."""
        assert _pp(src) == expected

    # Inputs where the unwrap must NOT fire — no math delimiters, or the span
    # is inside a fence where the source is being shown literally.
    @pytest.mark.parametrize(
        "text, must_contain",
        [
            pytest.param(
                "Use `quality_threshold` to filter.",
                "Use `quality_threshold` to filter.",
                id="plain-code-span-untouched",
            ),
            pytest.param(
                "```\nWrap math like `$x^2$` in backticks.\n```",
                "`$x^2$`",
                id="math-in-fence-untouched",
            ),
        ],
    )
    def test_no_unwrap_when_inapplicable(self, text: str, must_contain: str) -> None:
        """Non-math code spans and fenced examples keep their backticks."""
        assert must_contain in _pp(text)

    def test_math_in_pipe_table_cell(self) -> None:
        """The unwrap also applies inside pipe-table cells (line-level pass)."""
        text = "| Knob | Range |\n|---|---|\n| `quality_threshold $\\in [0,1]$` | tight |\n"
        result = _pp(text)
        assert "$\\text{quality threshold} \\in [0,1]$" in result
        assert "`quality_threshold" not in result


# ──────────────────────────────────────────────────────────────────
# --skip-phase / md2star_skip plumbing
# ──────────────────────────────────────────────────────────────────


class TestSkipPhase:
    """Phases can be disabled per-call or via YAML front-matter."""

    def test_skip_image_widths_via_arg(self) -> None:
        """``skip_phases=['image_widths']`` leaves bare images untouched."""
        result = _pp("![](/abs/img.png)", skip_phases=["image_widths"])
        assert "{width=100%}" not in result
        assert "![](/abs/img.png)" in result

    def test_skip_language_via_arg(self) -> None:
        """``skip_phases=['language']`` suppresses YAML lang/date_format injection."""
        text = "Ceci est un texte avec le, la, les, et, est."
        # inject_metadata=True so the language phase would fire if not skipped.
        result = _pp(text, inject_metadata=True, skip_phases=["language"])
        assert "lang:" not in result
        assert "date_format" not in result

    def test_skip_via_metadata(self) -> None:
        """``md2star_skip:`` in YAML front-matter is honored."""
        text = (
            "---\n"
            "md2star_skip: [image_widths]\n"
            "---\n\n"
            "![](/abs/img.png)\n"
        )
        result = _pp(text)
        assert "{width=100%}" not in result

    def test_unknown_phase_name_is_warned_not_fatal(self) -> None:
        """A nonsense phase name prints a warning to stderr but does not raise."""
        result = _pp("![](/abs/img.png)", skip_phases=["this_phase_does_not_exist"])
        # Unknown name → no effect; image widths still get injected.
        assert "{width=100%}" in result


# ──────────────────────────────────────────────────────────────────
# Language detection heuristic
# ──────────────────────────────────────────────────────────────────


class TestLanguageDetection:
    """Tests for the zero-dependency language guessing heuristic.

    Skipped if ``langdetect`` is not installed in the active env. The
    feature itself degrades gracefully (no metadata injection), so the
    skip avoids fake reds for users who only installed the core deps.
    """

    pytestmark = pytest.mark.skipif(
        # importlib.util.find_spec is the cheap form of "would `import langdetect` work";
        # actually importing it eagerly would pollute the test module.
        __import__("importlib.util", fromlist=["util"]).find_spec("langdetect") is None,
        reason="langdetect not installed; language metadata is optional",
    )

    # Stop-word-heavy text in each language must inject the right ``lang:`` tag;
    # a pre-declared lang must win over detection (no overwrite).
    @pytest.mark.parametrize(
        "text, present, absent",
        [
            pytest.param(
                "This is a simple text that has words like the and to in it.",
                "lang: en-US",
                None,
                id="english-detected",
            ),
            pytest.param(
                "Ceci est un texte avec le, la, les, et, est.",
                "lang: fr-FR",
                None,
                id="french-detected",
            ),
            pytest.param(
                "---\nlang: de-DE\n---\n\nEnglish words like the and to.",
                "lang: de-DE",
                "lang: en-US",
                id="existing-lang-respected",
            ),
        ],
    )
    def test_language_injection(self, text: str, present: str, absent: str | None) -> None:
        """Language metadata is injected from stop words, but never overwrites an
        explicit ``lang:`` already present in the front-matter."""
        # Metadata injection stays ON here (the feature under test); only
        # linting is disabled.
        result = _pp(text, inject_metadata=True)
        assert present in result
        if absent is not None:
            assert absent not in result
