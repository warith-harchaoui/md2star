"""
test_preprocessing.py — Unit tests for md2star.preprocessing.

Tests for the ``preprocess_markdown`` function, which runs the full
preprocessor pipeline (list spacing, HTML→pipe-table conversion, mermaid
rendering, math unwrapping, image normalization, PPTX slide isolation, …).

A shared ``conftest.py`` fixture redirects the on-disk cache to a fresh
``tmp_path`` for every test, so SVG/raster artifacts land in a known
location and do not pollute the user's real ``$XDG_CACHE_HOME/md2star/``.
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


# ──────────────────────────────────────────────────────────────────
# Basic / edge-case tests
# ──────────────────────────────────────────────────────────────────


class TestPreprocessMarkdownBasic:
    """Tests for trivial and edge-case inputs."""

    def test_empty_string(self) -> None:
        """Empty input should return an empty string."""
        # Edge case: function must handle empty input gracefully
        assert preprocess_markdown("", inject_metadata=False, lint_enabled=False) == ""

    def test_no_lists(self) -> None:
        """Content without any list items should pass through unchanged."""
        # No list markers present → no transformations should occur
        text = "Hello\nworld\n\nParagraph two."
        assert preprocess_markdown(text, inject_metadata=False, lint_enabled=False) == text

    def test_blank_lines_only(self) -> None:
        """A string of blank lines should pass through unchanged."""
        # Edge case: only whitespace, no actual content
        text = "\n\n\n"
        assert preprocess_markdown(text, inject_metadata=False, lint_enabled=False) == text


# ──────────────────────────────────────────────────────────────────
# Unordered list tests
# ──────────────────────────────────────────────────────────────────


class TestUnorderedLists:
    """Tests for dash, star, and plus-style list markers."""

    def test_blank_line_inserted_before_dash_item(self) -> None:
        """A blank line should be inserted when text precedes a dash list."""
        # Common case: paragraph followed by list needs spacing for Pandoc
        result = preprocess_markdown("Hello\n- item", inject_metadata=False, lint_enabled=False)
        assert result == "Hello\n\n- item"

    def test_blank_line_inserted_before_star_item(self) -> None:
        """Works with asterisk markers too."""
        # Markdown supports multiple unordered list markers
        result = preprocess_markdown("Hello\n* item", inject_metadata=False, lint_enabled=False)
        assert result == "Hello\n\n* item"

    def test_blank_line_inserted_before_plus_item(self) -> None:
        """Works with plus markers too."""
        # Plus (+) is another valid unordered list marker
        result = preprocess_markdown("Hello\n+ item", inject_metadata=False, lint_enabled=False)
        assert result == "Hello\n\n+ item"

    def test_no_double_blank_line(self) -> None:
        """If a blank line already precedes a list item, no extra is added."""
        # Idempotency: don't add blank lines if one already exists
        text = "Hello\n\n- item"
        assert preprocess_markdown(text, inject_metadata=False, lint_enabled=False) == text

    def test_consecutive_items_get_blank_lines(self) -> None:
        """Each consecutive list item should be separated by a blank line."""
        # Converts "tight" lists to "loose" lists for better DOCX/PPTX spacing
        result = preprocess_markdown("- a\n- b\n- c", inject_metadata=False, lint_enabled=False)
        assert result == "- a\n\n- b\n\n- c"


# ──────────────────────────────────────────────────────────────────
# Ordered list tests
# ──────────────────────────────────────────────────────────────────


class TestOrderedLists:
    """Tests for numbered list markers (1., 2., …)."""

    def test_ordered_list_item(self) -> None:
        """Numbered list items should also get blank lines inserted."""
        # Ordered lists use the same spacing logic as unordered lists
        result = preprocess_markdown("Intro\n1. First\n2. Second", inject_metadata=False, lint_enabled=False)
        assert result == "Intro\n\n1. First\n\n2. Second"

    def test_multi_digit_numbers(self) -> None:
        """Multi-digit numbers (10., 100., …) should still be matched."""
        # Regex must handle numbers > 9 correctly
        result = preprocess_markdown("Intro\n10. Tenth", inject_metadata=False, lint_enabled=False)
        assert result == "Intro\n\n10. Tenth"


# ──────────────────────────────────────────────────────────────────
# Nested list tests
# ──────────────────────────────────────────────────────────────────


class TestNestedLists:
    """Tests for indented (nested) list items."""

    def test_nested_list_items(self) -> None:
        """Indented sub-items should also be separated by blank lines."""
        # Nested lists preserve indentation while adding spacing
        result = preprocess_markdown("- parent\n  - child", inject_metadata=False, lint_enabled=False)
        assert result == "- parent\n\n  - child"


# ──────────────────────────────────────────────────────────────────
# Code-block preservation tests
# ──────────────────────────────────────────────────────────────────


class TestCodeBlocks:
    """List-like syntax inside fenced code blocks must NOT be altered."""

    def test_code_block_preserved(self) -> None:
        """Lines inside ``` … ``` should not trigger blank-line injection."""
        # Critical: code examples often contain list-like syntax that must not be altered
        text = "```\n- not a list\n```"
        assert preprocess_markdown(text, inject_metadata=False, lint_enabled=False) == text

    def test_code_block_with_surrounding_text(self) -> None:
        """Code block between paragraphs: only real lists get spacing."""
        # Mixed content: code block contains list-like syntax, followed by a real list
        text = "Before\n```\n- code\n```\nAfter\n- real list"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        # The "- code" inside the fence should be untouched (code preservation)
        assert "```\n- code\n```" in result
        # The real list item after the fence should get a blank line (list formatting)
        assert "After\n\n- real list" in result


# ──────────────────────────────────────────────────────────────────
# Mixed content tests
# ──────────────────────────────────────────────────────────────────


class TestMixedContent:
    """Tests combining headings, paragraphs, lists, and code blocks."""

    def test_heading_then_list(self) -> None:
        """A heading followed by a list should get a blank line."""
        # Headings are treated like paragraphs: need spacing before lists
        result = preprocess_markdown("## Heading\n- item", inject_metadata=False, lint_enabled=False)
        assert result == "## Heading\n\n- item"

    def test_paragraph_list_paragraph(self) -> None:
        """Paragraph → list → paragraph round-trip."""
        # Complex scenario: multiple list items between paragraphs
        text = "Intro\n- a\n- b\nOutro"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "Intro\n\n- a\n\n- b\nOutro" == result


# ──────────────────────────────────────────────────────────────────
# Mermaid Block tests
# ──────────────────────────────────────────────────────────────────


class TestMermaidBlocks:
    """Tests evaluating local Mermaid rendering pipeline."""

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    def test_mermaid_renders_success(self, mock_fetch) -> None:
        """A valid mermaid block is substituted with the rendered PNG absolute path."""
        mock_fetch.return_value = "/absolute/dummy.png"
        text = "Intro\n```mermaid\ngraph TD;\n    A-->B\n```\nOutro"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "![](/absolute/dummy.png)" in result
        assert "```mermaid" not in result

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    def test_mermaid_renders_fallback(self, mock_fetch) -> None:
        """A failed mermaid render falls back gracefully without modifying source."""
        mock_fetch.side_effect = Exception("Test Mermaid Error")
        text = "Intro\n```mermaid\ngraph TD;\n    A-->B\n```\nOutro"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "```mermaid\ngraph TD;\n    A-->B\n```" in result
        assert "![](" not in result

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    def test_mermaid_wide_diagram_caps_width(self, mock_fetch, tmp_path) -> None:
        """A wider-than-tall PNG gets a ``{width=15cm}`` cap (height auto)."""
        from PIL import Image

        png = tmp_path / "wide.png"
        Image.new("RGB", (3000, 1000), "white").save(png)
        mock_fetch.return_value = str(png)
        text = "```mermaid\ngraph LR;\nA-->B\n```"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert f"![]({png}){{width=15cm}}" in result

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    def test_mermaid_tall_diagram_caps_height(self, mock_fetch, tmp_path) -> None:
        """A taller-than-wide PNG gets a ``{height=17cm}`` cap (width auto)."""
        from PIL import Image

        png = tmp_path / "tall.png"
        Image.new("RGB", (600, 2500), "white").save(png)
        mock_fetch.return_value = str(png)
        text = "```mermaid\ngraph TD;\nA-->B\n```"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert f"![]({png}){{height=17cm}}" in result

    @patch("md2star.preprocessing.pipeline.render_mermaid_local")
    def test_mermaid_unreadable_png_falls_back_to_width100(self, mock_fetch) -> None:
        """If Pillow cannot open the render, the ``{width=100%}`` fallback still applies."""
        mock_fetch.return_value = "/absolute/dummy.png"
        text = "```mermaid\ngraph TD;\nA-->B\n```"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "![](/absolute/dummy.png){width=100%}" in result


# ──────────────────────────────────────────────────────────────────
# A4-fitting image cap (applies to ALL bare images, not just mermaid)
# ──────────────────────────────────────────────────────────────────


class TestA4ImageCap:
    """Bare ``![](src)`` images are capped to A4 dimensions by aspect ratio."""

    def test_wide_image_caps_width(self, tmp_path) -> None:
        # Longest side ≤ 1600 px so process_image_assets leaves the path alone.
        from PIL import Image

        png = tmp_path / "wide.png"
        Image.new("RGB", (1500, 500), "white").save(png)
        text = f"Photo:\n\n![]({png})\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert f"![]({png}){{width=15cm}}" in result

    def test_tall_image_caps_height(self, tmp_path) -> None:
        from PIL import Image

        png = tmp_path / "tall.png"
        Image.new("RGB", (500, 1500), "white").save(png)
        text = f"Photo:\n\n![]({png})\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert f"![]({png}){{height=17cm}}" in result

    def test_remote_url_falls_back_to_width100(self) -> None:
        """URLs cannot be measured offline — fall back to the generic 100% width."""
        text = "![](https://example.invalid/cannot-fetch.png)\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "https://example.invalid/cannot-fetch.png){width=100%}" in result

    def test_existing_attrs_are_preserved(self) -> None:
        """Images that already declare ``{…}`` are left untouched."""
        text = "![](/path/to/img.png){width=5cm}\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "![](/path/to/img.png){width=5cm}" in result
        assert "{width=15cm}" not in result
        assert "{height=17cm}" not in result


# ──────────────────────────────────────────────────────────────────
# Bibliography & Citation tests
# ──────────────────────────────────────────────────────────────────


class TestBibliographyCitations:
    """Tests ensuring that Pandoc-style bibliography citations are preserved."""

    def test_citations_in_lists(self) -> None:
        """Citations inside lists should remain completely intact."""
        text = "Related works:\n- [@pearl2000]\n- See @smith2019 for details"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "Related works:\n\n- [@pearl2000]\n\n- See @smith2019 for details" == result

    def test_inline_citations(self) -> None:
        """Inline citations in regular text should not be touched."""
        text = "As proven by @einstein1905, this works.\n\nMore info [@turing1936]."
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert text == result


# ──────────────────────────────────────────────────────────────────
# HTML table conversion tests
# ──────────────────────────────────────────────────────────────────


class TestHtmlTables:
    """Tests that HTML <table> blocks are converted to Markdown pipe-tables."""

    def test_simple_table(self) -> None:
        """A basic two-column HTML table should become a Markdown pipe-table."""
        html = (
            "<table><tr><th>Name</th><th>Value</th></tr>"
            "<tr><td>Alice</td><td>42</td></tr></table>"
        )
        result = preprocess_markdown(html, inject_metadata=False, lint_enabled=False)
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
        result = preprocess_markdown(html, inject_metadata=False, lint_enabled=False)
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
        result = preprocess_markdown(html, inject_metadata=False, lint_enabled=False)
        assert "| 1" in result
        assert "| 3" in result

    def test_table_separator_row(self) -> None:
        """Output must contain a separator line (---)."""
        html = "<table><tr><th>Col</th></tr><tr><td>data</td></tr></table>"
        result = preprocess_markdown(html, inject_metadata=False, lint_enabled=False)
        assert "|---" in result or "|--" in result

    def test_non_table_html_untouched(self) -> None:
        """Non-table HTML (e.g. <div>) should pass through unmodified."""
        text = "<div>Hello</div>"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "<div>Hello</div>" in result


# ──────────────────────────────────────────────────────────────────
# Pipe-table separator normalization tests
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
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        sep_line = [ln for ln in result.split("\n") if ln.startswith("|") and set(ln) <= set("|-: ")][0]
        cells = [c for c in sep_line.strip("|").split("|")]
        assert len(cells) == 3
        # Middle cell must be the widest, by a lot.
        assert len(cells[1]) > len(cells[0]) * 5
        assert len(cells[1]) > len(cells[2]) * 5
        # Total dashes must exceed Pandoc's --columns default (72) so widths take effect.
        assert sum(len(c) for c in cells) > 72

    def test_blank_line_after_table(self) -> None:
        """A paragraph glued to a table must be split off by a blank line."""
        text = "| A | B |\n|---|---|\n| 1 | 2 |\nNext paragraph."
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "| 1 | 2 |\n\nNext paragraph." in result

    def test_alignment_markers_preserved(self) -> None:
        """``:---:`` / ``---:`` / ``:---`` alignment markers must survive rewriting."""
        text = "| L | C | R |\n|:---|:---:|---:|\n| 1 | 2 | 3 |\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        sep_line = [ln for ln in result.split("\n") if ln.startswith("|") and set(ln) <= set("|-: ")][0]
        cells = sep_line.strip("|").split("|")
        assert cells[0].startswith(":") and not cells[0].endswith(":")
        assert cells[1].startswith(":") and cells[1].endswith(":")
        assert cells[2].endswith(":") and not cells[2].startswith(":")

    def test_idempotent(self) -> None:
        """Running preprocessing twice should produce the same output."""
        text = "| A | B |\n|---|---|\n| 1 | 2 |\n\nAfter."
        once = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        twice = preprocess_markdown(once, inject_metadata=False, lint_enabled=False)
        assert once == twice

    def test_table_in_code_block_untouched(self) -> None:
        """A pipe-table-looking block inside a fenced code block must not be rewritten."""
        text = "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
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
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
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
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "​" not in result

    def test_long_cell_gets_br_breaks(self) -> None:
        """A >120 char cell is broken at sentence boundaries with ``<br/>``."""
        long_cell = (
            "This is the first sentence in the long cell. "
            "This is the second sentence in the long cell. "
            "This is the third sentence so the total exceeds the wrap threshold."
        )
        text = f"| A | B |\n|---|---|\n| short | {long_cell} |\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "<br/>" in result
        # All visible content preserved (modulo whitespace shuffling).
        for fragment in ("first sentence", "second sentence", "third sentence"):
            assert fragment in result

    def test_short_cell_not_wrapped(self) -> None:
        """A short cell must not get any ``<br/>`` inserted."""
        text = "| A | B |\n|---|---|\n| short | a brief explanation |\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "<br" not in result

    def test_code_span_in_cell_preserved(self) -> None:
        """Backtick code spans inside a cell are left exactly as-written."""
        # The soft-break pass must skip code spans so identifiers inside backticks
        # still render as a single ``<w:t>`` run with no injected characters.
        text = (
            "| Variant | Code |\n"
            "|---|---|\n"
            "| heuristic | `ROITELET_ROUTER_long_constant_name_here` |\n"
        )
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
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
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        # Zero-width space (U+200B) must NOT appear inside the math chunk.
        assert "$\\alpha_{long_subscript_name_here}$" in result
        assert "​" not in result.split("$")[1]


# ──────────────────────────────────────────────────────────────────
# Image width auto-injection tests
# ──────────────────────────────────────────────────────────────────


class TestImageWidths:
    """Tests that bare image links get {width=100%} appended."""

    def test_bare_image_gets_width(self) -> None:
        """An image with no attributes should receive {width=100%}."""
        text = "![alt](/abs/path/to/image.png)"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "![alt](/abs/path/to/image.png){width=100%}" in result

    def test_image_with_existing_width_unchanged(self) -> None:
        """An image that already specifies a width must not be double-decorated."""
        text = "![alt](/abs/path/to/image.png){width=50%}"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "{width=100%}" not in result
        assert "{width=50%}" in result

    def test_empty_alt_image(self) -> None:
        """Images with empty alt text also need width injection."""
        text = "![](https://example.com/img.jpg)"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "{width=100%}" in result


# ──────────────────────────────────────────────────────────────────
# Image path absolutization tests
# ──────────────────────────────────────────────────────────────────


class TestImagePathAbsolutization:
    """Relative image paths must be rewritten to absolute against ``base_dir``."""

    def test_relative_path_becomes_absolute(self, tmp_path) -> None:
        text = "![](images/foo.png)"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert f"![]({tmp_path}/images/foo.png)" in result

    def test_parent_relative_path_resolves(self, tmp_path) -> None:
        """``../`` segments must be normalized, not left literal."""
        sub = tmp_path / "sub"
        sub.mkdir()
        text = "![](../foo.png)"
        result = preprocess_markdown(
            text, base_dir=str(sub), inject_metadata=False, lint_enabled=False
        )
        assert f"![]({tmp_path}/foo.png)" in result

    def test_absolute_path_unchanged(self, tmp_path) -> None:
        text = "![](/already/absolute.png)"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert "![](/already/absolute.png)" in result
        assert str(tmp_path) + "/already" not in result

    def test_http_url_unchanged(self, tmp_path) -> None:
        """HTTP URLs must not be joined with base_dir even if download fails."""
        text = "![](https://nonexistent.invalid.tld/img.png)"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert "https://nonexistent.invalid.tld/img.png" in result
        assert f"{tmp_path}/https:" not in result

    def test_data_uri_unchanged(self, tmp_path) -> None:
        text = "![](data:image/png;base64,iVBORw0KGgo=)"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert "data:image/png;base64,iVBORw0KGgo=" in result

    def test_code_block_paths_untouched(self, tmp_path) -> None:
        """Image syntax inside fenced code blocks is example text, not a real ref."""
        text = "```\n![](relative/in/code.png)\n```"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert "![](relative/in/code.png)" in result
        assert f"{tmp_path}/relative/in/code.png" not in result

    def test_multiple_images_same_line(self, tmp_path) -> None:
        text = "![a](one.png) ![b](sub/two.png)"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert f"![a]({tmp_path}/one.png)" in result
        assert f"![b]({tmp_path}/sub/two.png)" in result

    def test_linked_image(self, tmp_path) -> None:
        """The image inside ``[![](img)](url)`` must still be absolutized."""
        text = "[![](thumb.png)](https://example.com)"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert f"![]({tmp_path}/thumb.png)" in result
        assert "https://example.com" in result

    def test_pipe_table_cell_image_absolutized(self, tmp_path) -> None:
        """Images inside table cells must also resolve against base_dir.

        ``normalize_pipe_tables`` sprinkles zero-width spaces into table
        contents for soft-wrapping, so we strip them before checking.
        """
        text = (
            "| col |\n"
            "|-----|\n"
            "| ![](cell.png) |\n"
        )
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        ).replace("​", "")
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
        svg = self._make_svg(tmp_path)
        text = f"![logo]({svg.name})"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
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
        svg = self._make_svg(tmp_path, "diagram.svg")
        text = f'<img src="{svg.name}" alt="diagram" width="100%">'
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert "diagram.svg" not in result
        # PNG lands in the cache, not next to the source.
        cached_pngs = list(cache_dir("resized").glob("*_max*.png"))
        assert any(str(p) in result for p in cached_pngs)

    def test_oversized_raster_downscaled(self, tmp_path) -> None:
        from PIL import Image as PILImage

        big = tmp_path / "big.png"
        PILImage.new("RGB", (3200, 1600), color=(0, 128, 255)).save(big)
        text = f"![]({big.name})"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        cached = list(cache_dir("resized").glob("*_max1600.png"))
        assert cached, "expected a downscaled copy in the resized cache"
        with PILImage.open(cached[0]) as resized:
            w, h = resized.size
        assert max(w, h) == 1600
        # 3200/1600 = 2× downscale, so the shorter side should land at 800.
        assert min(w, h) == 800
        assert str(cached[0]) in result

    def test_small_raster_passes_through(self, tmp_path) -> None:
        from PIL import Image as PILImage

        small = tmp_path / "small.png"
        PILImage.new("RGB", (400, 300), color=(255, 0, 0)).save(small)
        text = f"![]({small.name})"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert str(small) in result
        # Nothing should have landed in the cache for an under-threshold image.
        assert not list(cache_dir("resized").glob("*"))

    def test_url_image_untouched(self, tmp_path) -> None:
        """The asset processor must not try to download / convert URLs."""
        text = "![](https://example.invalid/img.svg)"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
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
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert "<p" not in result and "<img" not in result
        assert f"![hero shot]({img})" in result
        assert "{width=100%}" in result

    def test_html_img_inside_fenced_code_preserved(self, tmp_path) -> None:
        """``<img>`` shown inside a code fence is example text, not a real ref."""
        text = "```\n<img src=\"shown-as-code.png\">\n```"
        result = preprocess_markdown(
            text, base_dir=str(tmp_path), inject_metadata=False, lint_enabled=False
        )
        assert '<img src="shown-as-code.png">' in result


# ──────────────────────────────────────────────────────────────────
# Pipe-table column-width slack for single-word columns
# ──────────────────────────────────────────────────────────────────


class TestSingleWordColumnSlack:
    """Single-word columns get extra width because they can't wrap."""

    @staticmethod
    def _separator_dashes(table_md: str) -> list[int]:
        """Return the dash-count of each column in the separator row."""
        result = preprocess_markdown(
            table_md, inject_metadata=False, lint_enabled=False
        )
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
        once = preprocess_markdown(
            table, inject_metadata=False, lint_enabled=False
        )
        twice = preprocess_markdown(
            once, inject_metadata=False, lint_enabled=False
        )
        assert once == twice, "single-word slack must not compound across runs"


# ──────────────────────────────────────────────────────────────────
# PPTX slide isolation tests
# ──────────────────────────────────────────────────────────────────


class TestPptxSlideIsolation:
    """Tables and images on a populated slide should be split onto fresh slides."""

    def test_table_after_prose_gets_own_slide(self) -> None:
        """A pipe-table that follows prose gets a synthetic blank ``##`` inserted."""
        text = (
            "## Section\n\n"
            "Some intro prose.\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n"
        )
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        # A new blank ``##`` slide marker must appear between the prose and the
        # table so Pandoc renders the table on its own PPTX slide.
        lines = result.split("\n")
        prose_idx = next(i for i, ln in enumerate(lines) if "intro prose" in ln)
        table_idx = next(i for i, ln in enumerate(lines) if ln.startswith("| A"))
        between = lines[prose_idx + 1 : table_idx]
        assert any(ln.strip() == "##" for ln in between)

    def test_two_tables_in_one_section_each_get_own_slide(self) -> None:
        """A second table in the same section is split off onto a new slide."""
        text = (
            "## Section\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "| C | D |\n|---|---|\n| 3 | 4 |\n"
        )
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        lines = result.split("\n")
        first_table = next(i for i, ln in enumerate(lines) if ln.startswith("| A"))
        second_table = next(i for i, ln in enumerate(lines) if ln.startswith("| C"))
        between = lines[first_table + 1 : second_table]
        assert any(ln.strip() == "##" for ln in between)

    def test_first_table_in_section_not_isolated(self) -> None:
        """A table that opens a section directly is left where it is."""
        text = "## Section\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        # No bare ``##`` slide marker should appear between the heading and the
        # table because the section starts with the table.
        lines = result.split("\n")
        heading_idx = next(i for i, ln in enumerate(lines) if ln.startswith("## "))
        table_idx = next(i for i, ln in enumerate(lines) if ln.startswith("| A"))
        between = lines[heading_idx + 1 : table_idx]
        assert not any(ln.strip() == "##" for ln in between)

    def test_pipe_table_inside_code_block_not_treated_as_table(self) -> None:
        """A pipe-table-shaped block inside a fenced code block does not trigger isolation."""
        text = (
            "## Section\n\n"
            "Some prose.\n\n"
            "```\n| A | B |\n|---|---|\n| 1 | 2 |\n```\n"
        )
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
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
        once = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        twice = preprocess_markdown(once, inject_metadata=False, lint_enabled=False)
        assert once == twice
        # And exactly one blank separator was inserted, not a growing pile.
        assert once.count("\n##\n") + once.count("\n## \n") <= 1


# ──────────────────────────────────────────────────────────────────
# Math-in-code unwrapping tests
# ──────────────────────────────────────────────────────────────────


class TestMathInCodeSpans:
    """Backticks wrapping LaTeX math should be rewritten into proper math.

    Pandoc renders backtick content verbatim, so ``\\`$x^2$\\``` would
    otherwise come out as a monospaced ``$x^2$`` literal instead of as
    rendered math. The preprocessor unwraps pure-math spans and merges
    mixed text/math spans into a single math expression.
    """

    def test_pure_inline_math_unwrapped(self) -> None:
        """A code span whose content is exactly ``$x^2$`` becomes ``$x^2$``."""
        result = preprocess_markdown("`$x^2$`", inject_metadata=False, lint_enabled=False)
        assert result == "$x^2$"

    def test_pure_display_math_unwrapped(self) -> None:
        """Display math ``$$..$$`` survives the unwrap with both delimiter pairs."""
        result = preprocess_markdown("`$$x^2$$`", inject_metadata=False, lint_enabled=False)
        assert result == "$$x^2$$"

    def test_paren_math_unwrapped(self) -> None:
        r"""The ``\(..\)`` inline form is also recognized as math."""
        result = preprocess_markdown(r"`\(x^2\)`", inject_metadata=False, lint_enabled=False)
        assert result == r"\(x^2\)"

    def test_bracket_math_unwrapped(self) -> None:
        r"""The ``\[..\]`` display form is also recognized as math."""
        result = preprocess_markdown(r"`\[x^2\]`", inject_metadata=False, lint_enabled=False)
        assert result == r"\[x^2\]"

    def test_snake_case_identifier_with_math_merged(self) -> None:
        """The headline case: snake_case prose mixed with math collapses to one ``$..$``."""
        # ``quality_threshold`` reads as the words "quality threshold" — the
        # underscore would be parsed as a subscript inside math.
        text = "sharing one `quality_threshold $\\in [0,1]$` knob"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert result == "sharing one $\\text{quality threshold} \\in [0,1]$ knob"

    def test_text_after_math_merged(self) -> None:
        """Text *after* the math chunk inside a code span is wrapped in \\text{}."""
        text = "`$x^2$ when x is real`"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert result == "$x^2 \\text{when x is real}$"

    def test_multiple_math_chunks_in_one_code_span(self) -> None:
        """Multiple math chunks interleaved with text are merged into one expression."""
        text = "`if $a$ then $b$`"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert result == "$\\text{if} a \\text{then} b$"

    def test_plain_text_code_span_untouched(self) -> None:
        """A code span without any math delimiters keeps its backticks."""
        text = "Use `quality_threshold` to filter."
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert result == text

    def test_math_inside_fenced_block_untouched(self) -> None:
        """Backticked math inside a fenced code block stays verbatim — it's a code sample."""
        # Inside a fence the user is showing literal Markdown source, so we
        # must not rewrite it.
        text = "```\nWrap math like `$x^2$` in backticks.\n```"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "`$x^2$`" in result

    def test_math_in_pipe_table_cell(self) -> None:
        """The unwrap also applies inside pipe-table cells (line-level pass)."""
        text = "| Knob | Range |\n|---|---|\n| `quality_threshold $\\in [0,1]$` | tight |\n"
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "$\\text{quality threshold} \\in [0,1]$" in result
        assert "`quality_threshold" not in result


# ──────────────────────────────────────────────────────────────────
# --skip-phase / md2star_skip plumbing
# ──────────────────────────────────────────────────────────────────


class TestSkipPhase:
    """Phases can be disabled per-call or via YAML front-matter."""

    def test_skip_image_widths_via_arg(self) -> None:
        """``skip_phases=['image_widths']`` leaves bare images untouched."""
        text = "![](/abs/img.png)"
        result = preprocess_markdown(
            text,
            inject_metadata=False,
            lint_enabled=False,
            skip_phases=["image_widths"],
        )
        assert "{width=100%}" not in result
        assert "![](/abs/img.png)" in result

    def test_skip_language_via_arg(self) -> None:
        """``skip_phases=['language']`` suppresses YAML lang/date_format injection."""
        text = "Ceci est un texte avec le, la, les, et, est."
        result = preprocess_markdown(
            text,
            inject_metadata=True,
            lint_enabled=False,
            skip_phases=["language"],
        )
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
        result = preprocess_markdown(text, inject_metadata=False, lint_enabled=False)
        assert "{width=100%}" not in result

    def test_unknown_phase_name_is_warned_not_fatal(self) -> None:
        """A nonsense phase name prints a warning to stderr but does not raise."""
        text = "![](/abs/img.png)"
        result = preprocess_markdown(
            text,
            inject_metadata=False,
            lint_enabled=False,
            skip_phases=["this_phase_does_not_exist"],
        )
        # Unknown name → no effect; image widths still get injected.
        assert "{width=100%}" in result


# ──────────────────────────────────────────────────────────────────
# Language Detection heuristic tests
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

    def test_english_detection(self) -> None:
        """Text with many English stop words gets en-US injected."""
        text = "This is a simple text that has words like the and to in it."
        result = preprocess_markdown(text, lint_enabled=False)
        assert "lang: en-US" in result

    def test_french_detection(self) -> None:
        """Text with French stop words gets fr-FR injected."""
        text = "Ceci est un texte avec le, la, les, et, est."
        result = preprocess_markdown(text, lint_enabled=False)
        assert "lang: fr-FR" in result

    def test_existing_lang_respected(self) -> None:
        """If a lang property is already in the YAML, it should not be overwritten."""
        text = "---\nlang: de-DE\n---\n\nEnglish words like the and to."
        result = preprocess_markdown(text, lint_enabled=False)
        assert "lang: de-DE" in result
        assert "lang: en-US" not in result
