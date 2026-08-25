"""
test_preprocessing.py — Functional scenario tests for md2star.preprocessing.

Exercises the ``preprocess_markdown`` entry point, which runs the full
preprocessor pipeline (list spacing, HTML→pipe-table conversion, mermaid
rendering, math unwrapping, image normalization, PPTX slide isolation,
language detection, …) — but stays PANDOC-FREE and fast: it never touches
the md2docx / pandoc path.

Design (coding-standard rule 13 — "prefer functional tests that cover several
use cases end-to-end"):

* The bulk of coverage comes from a handful of *scenario* tests. Each builds
  one realistic document that combines many features at once (headings, loose
  lists, a table, a local image, a mermaid block, inline/display math, …),
  runs it through ``preprocess_markdown`` ONCE, then asserts every
  transformation. One scenario replaces a dozen single-feature micro-tests
  and reads like real usage:

    - ``test_full_document_docx_scenario``      — the "kitchen-sink" DOCX doc.
    - ``test_full_document_pptx_scenario``      — same features, PPTX slide split.
    - ``test_image_handling_scenario``          — every image class in one doc.
    - ``test_table_rewriting_scenario``         — HTML→pipe + separator + wrapping.
    - ``test_math_protection_scenario``         — every math-unwrap branch.
    - ``test_skip_phase_scenario``              — per-call / front-matter opt-out.
    - ``test_language_detection_scenario``      — stop-word language guessing.

* Genuine value-families (three list markers, four math delimiters, three
  "not re-rooted" ref kinds, the A4 aspect-ratio cap at both orientations)
  stay ONE function via ``@pytest.mark.parametrize`` so every (input,
  expected) pair remains a distinct named case.

* Genuinely tricky EDGE cases that a broad scenario would not reliably hit —
  and one idempotency regression pin — are KEPT as their own targeted tests
  (see the "targeted edge cases" section) rather than folded into a scenario,
  so their assertions stay sharp.

A shared ``conftest.py`` fixture redirects the on-disk cache to a fresh
``tmp_path`` for every test, so SVG / raster / mermaid artifacts land in a
known location and never pollute the user's real ``$MD2STAR_CACHE_DIR``.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import re
from unittest.mock import patch

import pytest

from md2star.cache import cache_dir
from md2star.preprocessing import preprocess_markdown

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────


def _module_importable(name: str) -> bool:
    """Return True iff ``import name`` would succeed in this venv.

    Parameters
    ----------
    name : str
        Dotted module name to probe.

    Returns
    -------
    bool
        Whether the module can be imported without importing it.
    """
    import importlib.util

    return importlib.util.find_spec(name) is not None


def _pp(text: str, **kwargs) -> str:
    """Run ``preprocess_markdown`` with the test-default flags.

    Almost every test disables metadata injection and linting so it can
    assert on the structural transform alone. This helper centralizes
    those defaults; callers override via ``**kwargs`` when they need the
    language / metadata passes on.

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


def _separator_dashes(result: str) -> list[int]:
    """Return the per-column dash count of a pipe-table separator row.

    Parameters
    ----------
    result : str
        Preprocessed markdown containing exactly one pipe-table.

    Returns
    -------
    list[int]
        Per-column count of ``-`` characters (alignment colons excluded,
        since they add no visual width).
    """
    sep_line = next(ln for ln in result.split("\n") if re.match(r"^\|[-:|]+\|$", ln.strip()))
    inner = sep_line.strip()[1:-1]
    return [cell.count("-") for cell in inner.split("|")]


def _marker_between(result: str, start_pred, end_pred) -> bool:
    """Return True iff a bare ``##`` slide marker sits between two lines.

    Parameters
    ----------
    result : str
        Preprocessed markdown to scan.
    start_pred, end_pred : Callable[[str], bool]
        Predicates picking the first line of the opening / closing anchor.

    Returns
    -------
    bool
        Whether any line strictly between the anchors is a lone ``##``.
    """
    lines = result.split("\n")
    start = next(i for i, ln in enumerate(lines) if start_pred(ln))
    end = next(i for i, ln in enumerate(lines) if end_pred(ln))
    return any(ln.strip() == "##" for ln in lines[start + 1 : end])


_HAS_SVG_BACKEND = __import__("shutil").which("rsvg-convert") is not None or _module_importable(
    "cairosvg"
)


# ──────────────────────────────────────────────────────────────────
# Full-document scenarios (the bulk of coverage)
# ──────────────────────────────────────────────────────────────────


@patch("md2star.preprocessing.pipeline.render_mermaid_local")
def test_full_document_docx_scenario(mock_mermaid, tmp_path) -> None:
    """Run a realistic multi-feature DOCX document through the pipeline once.

    This is the "kitchen-sink" scenario: a single document combining a
    heading, a citation-bearing loose list (all three bullet markers), a
    fenced code block that must be left alone, an HTML table, a bare local
    image, a mermaid diagram, and inline/display math. One pass must apply
    every transformation correctly and in mutual isolation.

    Parameters
    ----------
    mock_mermaid : unittest.mock.MagicMock
        Patched ``render_mermaid_local`` so no real mermaid binary is needed.
    tmp_path : pathlib.Path
        Pytest temp dir; hosts the measurable local image.
    """
    from PIL import Image

    # A wider-than-tall local PNG so the A4 cap picks a width limit.
    photo = tmp_path / "figure.png"
    Image.new("RGB", (1500, 500), "white").save(photo)
    # Mermaid renders to an absolute PNG path (unreadable → width=100% branch).
    mock_mermaid.return_value = "/absolute/diagram.png"

    doc = (
        "# Report Title\n"
        "Intro paragraph citing @einstein1905 and [@turing1936].\n"
        "Findings:\n"
        "- First point [@pearl2000]\n"
        "* Second point\n"
        "+ Third point\n"
        "```\n"
        "- this dash is code, not a list item\n"
        "```\n"
        "<table><tr><th>Name</th><th>Score</th></tr>"
        "<tr><td>Alice</td><td>42</td></tr></table>\n"
        f"![figure]({photo})\n"
        "```mermaid\ngraph TD;\n    A-->B\n```\n"
        "The formula $E = mc^2$ holds, and display math follows:\n"
        "$$\\int_0^1 x\\,dx$$\n"
    )
    result = _pp(doc)

    # List spacing: every marker kind (-, *, +) gains a blank line so Pandoc
    # reads a loose list, while citations survive verbatim.
    assert "Findings:\n\n- First point [@pearl2000]" in result
    assert "\n\n* Second point" in result
    assert "\n\n+ Third point" in result
    # Inline citations in prose are untouched.
    assert "@einstein1905" in result and "[@turing1936]" in result

    # Code-block preservation: the list-like line inside the fence is NOT
    # spaced out (would corrupt a code example otherwise).
    assert "```\n- this dash is code, not a list item\n```" in result

    # HTML table → Markdown pipe-table: the raw <table> is gone and the
    # header/data cells appear as pipe cells with a separator row.
    assert "<table>" not in result
    assert "| Name" in result and "| Alice" in result
    assert any(set(ln) <= set("|-: ") and ln.startswith("|") for ln in result.split("\n"))

    # Local image A4 cap: a 1500×500 (wide) PNG caps width, height auto.
    assert f"![figure]({photo}){{width=15cm}}" in result

    # Mermaid: the fenced block is replaced by an image ref to the render;
    # an unreadable render path still gets the generic {width=100%} fallback.
    assert "```mermaid" not in result
    assert "![](/absolute/diagram.png){width=100%}" in result

    # Math is preserved as real math (delimiters intact), not mangled.
    assert "$E = mc^2$" in result
    assert "$$\\int_0^1 x\\,dx$$" in result


@patch("md2star.preprocessing.pipeline.render_mermaid_local")
def test_full_document_pptx_scenario(mock_mermaid) -> None:
    """Run a multi-block slide deck through the PPTX slide-isolation path.

    Same feature spirit as the DOCX scenario, but focused on PPTX per-slide
    isolation: a section that opens with prose and then carries *two* tables
    plus a mermaid image. The isolator must split each populated block onto
    its own slide by inserting bare ``##`` markers, while leaving the first
    block that directly opens a section where it is, and never treating a
    code-fenced pipe-table as a real table.

    Parameters
    ----------
    mock_mermaid : unittest.mock.MagicMock
        Patched ``render_mermaid_local`` so no real mermaid binary is needed.
    """
    mock_mermaid.return_value = "/absolute/slide-diagram.png"
    deck = (
        "## Opening Section\n\n"
        "Some intro prose that opens the slide.\n\n"
        "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
        "| C | D |\n|---|---|\n| 3 | 4 |\n\n"
        "## Second Section\n\n"
        "| E | F |\n|---|---|\n| 5 | 6 |\n\n"
        "Prose, then a fenced pseudo-table that must NOT split:\n\n"
        "```\n| X | Y |\n|---|---|\n| 9 | 8 |\n```\n"
    )
    result = _pp(deck)

    # A table following prose in a populated slide is pushed onto a fresh
    # slide: a bare ``##`` appears between the prose and the first table.
    assert _marker_between(
        result,
        lambda ln: "intro prose" in ln,
        lambda ln: ln.startswith("| A"),
    )
    # The SECOND table in the same section is likewise split off.
    assert _marker_between(
        result,
        lambda ln: ln.startswith("| A"),
        lambda ln: ln.startswith("| C"),
    )
    # A table that opens a section directly is left in place (no bare ## between
    # the heading and the table).
    assert not _marker_between(
        result,
        lambda ln: ln.startswith("## Second"),
        lambda ln: ln.startswith("| E"),
    )
    # A pipe-table-shaped block inside a code fence must NOT trigger a split:
    # no bare ``##`` may sit immediately before the fence.
    lines = result.split("\n")
    fence_idx = next(
        i
        for i, ln in enumerate(lines)
        if ln.strip() == "```" and "| X" in "".join(lines[i : i + 3])
    )
    assert lines[fence_idx - 1].strip() != "##"


def test_image_handling_scenario(tmp_path) -> None:
    """Run every image class through one document to pin the image passes.

    Combines, in one pass: a relative path (absolutized against ``base_dir``),
    a ``../`` parent-relative path (normalized), a bare local raster that is
    small enough to survive (measured → A4 cap), a remote URL (unmeasurable →
    {width=100%}), an image that already declares ``{…}`` (untouched), and an
    oversized raster (downscaled into the cache). This one scenario replaces a
    stack of single-image micro-tests.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest temp dir used as ``base_dir`` and as the raster source.
    """
    from PIL import Image as PILImage

    # A measurable, wider-than-tall local image (longest side ≤ 1600 so the
    # asset processor leaves the path alone and the A4 cap fires on it).
    (tmp_path / "images").mkdir()
    small = tmp_path / "images" / "small.png"
    PILImage.new("RGB", (1500, 500), "white").save(small)
    # An oversized raster (>1600) that must be downscaled into the cache.
    big = tmp_path / "big.png"
    PILImage.new("RGB", (3200, 1600), (0, 128, 255)).save(big)
    # A ../-relative image resolved against a sub-directory base_dir.
    sub = tmp_path / "sub"
    sub.mkdir()
    parent_img = tmp_path / "parent.png"
    PILImage.new("RGB", (300, 200), "red").save(parent_img)
    # A small raster referenced from INSIDE a table cell — exercises the
    # per-cell resize/absolutize pass, distinct from the top-level image pass.
    cell_img = tmp_path / "cell.png"
    PILImage.new("RGB", (200, 100), "green").save(cell_img)

    doc = (
        "![small](images/small.png)\n\n"
        f"![big]({big.name})\n\n"
        "![remote](https://example.invalid/cannot-fetch.png)\n\n"
        "![abs](/already/absolute.png)\n\n"
        "![data](data:image/png;base64,iVBORw0KGgo=)\n\n"
        "![fixed](/already/sized.png){width=5cm}\n\n"
        "| Figure |\n|--------|\n| ![](cell.png) |\n"
    )
    result = _pp(doc, base_dir=str(tmp_path))

    # Relative path → absolutized against base_dir; measurable wide image gets
    # the A4 width cap rather than the generic 100%.
    assert f"![small]({tmp_path}/images/small.png){{width=15cm}}" in result

    # Oversized raster → a downscaled cached sibling (aspect preserved: 3200×1600
    # halves to 1600×800), and the ref points at the cached copy.
    cached = list(cache_dir("resized").glob("*_max1600.png"))
    assert cached, "expected a downscaled copy in the resized cache"
    with PILImage.open(cached[0]) as resized:
        assert resized.size == (1600, 800)
    assert str(cached[0]) in result

    # Remote URL cannot be measured offline → generic {width=100%}, left as URL.
    assert "https://example.invalid/cannot-fetch.png){width=100%}" in result

    # Refs that are already resolvable are NEVER re-rooted under base_dir: an
    # absolute path, an http URL, and a data-URI all survive verbatim with no
    # base_dir prefix prepended. Each is a distinct "not a local relative path"
    # branch in the absolutizer.
    for ref, joined_prefix in (
        ("/already/absolute.png", "/already"),
        ("https://example.invalid/cannot-fetch.png", "https:"),
        ("data:image/png;base64,iVBORw0KGgo=", "data:"),
    ):
        assert ref in result
        assert f"{tmp_path}/{joined_prefix}" not in result

    # An image that already declares a width is not double-decorated.
    assert "![fixed](/already/sized.png){width=5cm}" in result
    assert "{width=15cm}" not in result.split("![fixed]")[1].split("\n")[0]

    # A table-cell image is absolutized/resized against base_dir too. The
    # normalizer sprinkles ZWSPs into cell content, so strip them first.
    stripped = result.replace("​", "")
    assert "(cell.png)" not in stripped
    assert str(tmp_path) in stripped.split("| Figure")[1]

    # Separately verify ../-relative resolution against a sub-dir base_dir.
    parent_res = _pp("![](../parent.png)", base_dir=str(sub))
    assert f"![]({tmp_path}/parent.png)" in parent_res


def test_table_rewriting_scenario() -> None:
    """Run one document that stresses every pipe-table rewriting rule.

    Combines HTML→pipe conversion with inline-HTML cell markers, multiple
    data rows, proportional separator widths, single-word column slack, a
    long cell that must be ``<br/>``-wrapped, a paragraph glued to a table
    that must be split off, and alignment-marker survival. One pass must
    satisfy all of them together.
    """
    long_desc = "A" * 140
    long_cell = (
        "This is the first sentence in the long cell. "
        "This is the second sentence in the long cell. "
        "This is the third sentence so the total exceeds the wrap threshold."
    )
    doc = (
        # HTML table with inline markup in cells + two data rows.
        "<table>"
        "<tr><th>Start</th><th>Role</th></tr>"
        "<tr><td><code>3 sec</code></td><td><strong>Operator</strong></td></tr>"
        "<tr><td>later</td><td><em>helper</em></td></tr>"
        "</table>\n\n"
        # A wide-middle-column pipe-table for proportional separator widths.
        "| ID | Description | Section |\n"
        "|:---|:---:|---:|\n"
        f"| C1 | {long_desc} | §6 |\n\n"
        # A table with a long cell + a glued trailing paragraph.
        f"| A | B |\n|---|---|\n| short | {long_cell} |\nNext paragraph.\n\n"
        # A cell image whose file does not exist: the per-cell resize pass must
        # leave the ref as-is rather than crash (missing-file fallback branch).
        "| Pic |\n|-----|\n| ![](does-not-exist.png) |\n"
    )
    result = _pp(doc)

    # HTML→pipe: raw table tags gone, inline <code>/<strong>/<em> become
    # Markdown markers so Pandoc styles the cell content.
    assert "<table>" not in result and "<code>" not in result
    assert "`3 sec`" in result
    assert "**Operator**" in result
    assert "*helper*" in result
    # Multiple data rows all survive.
    assert "| later" in result

    # Proportional separator + alignment survival: pick the aligned table's
    # separator row (the only one carrying alignment colons). Its 140-char
    # middle column must be far wider than its 2-char neighbours, total dashes
    # must clear Pandoc's 72-col default so widths take effect, and the three
    # alignment markers (:---, :---:, ---:) must survive the rewrite.
    aligned_sep = next(
        ln
        for ln in result.split("\n")
        if ln.startswith("|") and set(ln) <= set("|-: ") and ":" in ln
    )
    cells = aligned_sep.strip("|").split("|")
    mid = next(c for c in cells if len(c) > 30)
    others = [c for c in cells if len(c) <= 30]
    assert all(len(mid) > len(o) * 5 for o in others)
    assert sum(len(c) for c in cells) > 72
    assert any(c.startswith(":") and not c.endswith(":") for c in cells)
    assert any(c.startswith(":") and c.endswith(":") for c in cells)
    assert any(c.endswith(":") and not c.startswith(":") for c in cells)

    # A >120-char cell is broken at sentence boundaries with <br/>, content kept.
    assert "<br/>" in result
    for fragment in ("first sentence", "second sentence", "third sentence"):
        assert fragment in result
    # A paragraph glued to a table is split off by a blank line.
    assert re.search(r"\| .*\|\n\nNext paragraph\.", result)
    # A missing cell image is passed through untouched (no crash, no rewrite).
    assert "does-not-exist.png" in result.replace("​", "")


@patch("md2star.preprocessing.pipeline.render_mermaid_local")
def test_math_protection_scenario(mock_mermaid) -> None:
    """Run one document exercising every math-unwrap and math-protect branch.

    Pandoc renders backtick content verbatim, so ``\\`$x^2$\\``` would emit a
    monospaced literal instead of rendered math. This scenario checks that:
    pure-math code spans unwrap to bare math; a mixed text+math span collapses
    to one ``$…$`` with prose wrapped in ``\\text{}``; a plain (non-math) code
    span keeps its backticks; and a math span shown inside a fence is left as
    literal source.

    Parameters
    ----------
    mock_mermaid : unittest.mock.MagicMock
        Patched so an incidental mermaid block does not need a real binary.
    """
    mock_mermaid.return_value = "/absolute/m.png"
    doc = (
        "Inline pure math `$x^2$` and display `$$y^2$$`.\n\n"
        "Mixed span: sharing one `quality_threshold $\\in [0,1]$` knob.\n\n"
        "Plain code `quality_threshold` must stay a literal.\n\n"
        "```\nWrap math like `$z^2$` in backticks when documenting.\n```\n"
    )
    result = _pp(doc)

    # Pure-math code spans unwrap to bare math (inline + display forms).
    assert "$x^2$" in result and "`$x^2$`" not in result
    assert "$$y^2$$" in result

    # A mixed text+math span collapses into one $…$ expression: the snake_case
    # identifier reads as words in \text{} (so its underscore is not parsed as
    # a math subscript), merged with the real math chunk.
    assert "$\\text{quality threshold} \\in [0,1]$" in result

    # A plain code span with no math delimiters is left untouched.
    assert "`quality_threshold` must stay a literal." in result

    # A math span shown INSIDE a code fence is example source, not real math —
    # its backticks are preserved.
    assert "`$z^2$`" in result


def test_skip_phase_scenario() -> None:
    """Exercise the --skip-phase / md2star_skip opt-out plumbing end to end.

    Phases can be disabled per call (``skip_phases=[…]``) or via YAML
    front-matter (``md2star_skip: […]``). An unknown phase name is a warning,
    not a fatal error. All four behaviours are checked here because they share
    one dispatch path.
    """
    # Per-call skip of image_widths: a bare image is left undecorated.
    r1 = _pp("![](/abs/img.png)", skip_phases=["image_widths"])
    assert "{width=100%}" not in r1 and "![](/abs/img.png)" in r1

    # Front-matter skip is honored exactly like the per-call form.
    r2 = _pp("---\nmd2star_skip: [image_widths]\n---\n\n![](/abs/img.png)\n")
    assert "{width=100%}" not in r2

    # An unknown phase name warns but has no effect: widths still get injected.
    r3 = _pp("![](/abs/img.png)", skip_phases=["this_phase_does_not_exist"])
    assert "{width=100%}" in r3

    # Skipping the language phase suppresses lang / date_format injection even
    # with metadata injection turned on.
    fr = "Ceci est un texte avec le, la, les, et, est."
    r4 = _pp(fr, inject_metadata=True, skip_phases=["language"])
    assert "lang:" not in r4 and "date_format" not in r4


@pytest.mark.skipif(
    not _module_importable("langdetect"),
    reason="langdetect not installed; language metadata is optional",
)
def test_language_detection_scenario() -> None:
    """Language metadata is injected from stop words, never overwriting an
    explicit ``lang:`` already in the front-matter.

    Sweeps English detection, French detection, and the no-overwrite guard when
    a ``lang:`` is already declared.
    """
    cases = [
        ("This is a simple text that has words like the and to in it.", "lang: en-US", None),
        ("Ceci est un texte avec le, la, les, et, est.", "lang: fr-FR", None),
        ("---\nlang: de-DE\n---\n\nEnglish words like the and to.", "lang: de-DE", "lang: en-US"),
    ]
    for text, present, absent in cases:
        # Metadata injection stays ON here (the feature under test); linting off.
        result = _pp(text, inject_metadata=True)
        assert present in result
        if absent is not None:
            assert absent not in result


# ──────────────────────────────────────────────────────────────────
# Parametrized value-families (kept ONE function each)
# ──────────────────────────────────────────────────────────────────


def test_passthrough_unchanged() -> None:
    """Inputs with nothing to transform pass through byte-for-byte."""
    # Each guards a different "no transformation should fire" edge.
    for text in ("", "<div>Hello</div>"):
        assert _pp(text) == text


def test_blank_line_inserted_before_lists() -> None:
    """A blank line is inserted before a list item for every marker kind.

    Covers dash/star/plus markers, multi-digit ordered items (regex must handle
    numbers > 9), and indented sub-items — Pandoc needs the blank line to read a
    loose list.
    """
    cases = [
        ("Hello\n- item", "Hello\n\n- item"),
        ("Hello\n* item", "Hello\n\n* item"),
        ("Hello\n+ item", "Hello\n\n+ item"),
        ("Intro\n10. Tenth", "Intro\n\n10. Tenth"),  # multi-digit ordered
        ("- parent\n  - child", "- parent\n\n  - child"),  # nested indent kept
    ]
    for text, expected in cases:
        assert _pp(text) == expected


def test_pure_math_latex_delimiter_families() -> None:
    """The ``\\(..\\)`` and ``\\[..\\]`` forms unwrap from a pure-math code span.

    The ``$..$`` / ``$$..$$`` forms are covered by ``test_math_protection_scenario``;
    the LaTeX delimiters are separate recognizer branches pinned here.
    """
    for src, expected in [(r"`\(x^2\)`", r"\(x^2\)"), (r"`\[x^2\]`", r"\[x^2\]")]:
        assert _pp(src) == expected


def test_a4_cap_taller_than_wide_caps_height(tmp_path) -> None:
    """A taller-than-wide measurable image caps HEIGHT (width auto).

    The A4 fit-cap applies to ALL bare images. The wide/width orientation is
    already exercised by ``test_full_document_docx_scenario`` and
    ``test_image_handling_scenario``; this pins the complementary tall
    orientation, whose cap picks the height axis instead.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest temp dir hosting the image.
    """
    from PIL import Image

    png = tmp_path / "portrait.png"
    Image.new("RGB", (500, 1500), "white").save(png)
    result = _pp(f"Photo:\n\n![]({png})\n")
    assert f"![]({png}){{height=17cm}}" in result


# ──────────────────────────────────────────────────────────────────
# Targeted edge cases + regression pins (deliberately NOT folded into a
# scenario — a broad document would not reliably hit these, or the assertion
# would go murky if it did).
# ──────────────────────────────────────────────────────────────────


@patch("md2star.preprocessing.pipeline.render_mermaid_local")
def test_mermaid_render_failure_falls_back(mock_fetch) -> None:
    """A failed mermaid render leaves the source block untouched, no image.

    Edge case: the *failure* branch is hard to hit inside a broad scenario
    because the happy path already stubs a successful render. Kept standalone
    so the graceful-degradation contract stays explicit.

    Parameters
    ----------
    mock_fetch : unittest.mock.MagicMock
        Patched to raise, simulating a render error.
    """
    mock_fetch.side_effect = Exception("Test Mermaid Error")
    text = "Intro\n```mermaid\ngraph TD;\n    A-->B\n```\nOutro"
    result = _pp(text)
    # The original fenced source survives and no image ref is emitted.
    assert "```mermaid\ngraph TD;\n    A-->B\n```" in result
    assert "![](" not in result


def test_pipe_table_zwsp_soft_breaks_on_long_path() -> None:
    """Long unbreakable cell content gains zero-width spaces after / and _.

    Edge case: file-path-shaped strings longer than the 25-char threshold are
    made wrappable so narrow columns don't collapse to char-per-line. The
    ZWSP (U+200B) is invisible, so this needs a precise standalone assertion
    a broad scenario cannot phrase cleanly.
    """
    text = (
        "| Path | Notes |\n"
        "|---|---|\n"
        "| data/conversations/long_record_id.json | one per conversation |\n"
    )
    result = _pp(text)
    # A ZWSP is injected right after slashes and underscores in the long path.
    assert "/​" in result
    assert "_​" in result
    # Short content is left alone, and the visible path still reads intact.
    assert "one per conversation" in result
    assert "data/conversations/long_record_id.json" in result.replace("​", "")


def test_pipe_table_code_span_and_math_cells_not_soft_broken() -> None:
    """Backtick code spans and math in cells escape the soft-break pass.

    Edge case: the ZWSP soft-wrapper must SKIP code spans (so an identifier in
    backticks stays one ``<w:t>`` run) and math (so ``\\alpha_{…}`` keeps a
    clean subscript rather than a ZWSP-poisoned one). Two sharp, separate
    assertions that would be blurred inside a general table scenario.
    """
    code_cell = (
        "| Variant | Code |\n|---|---|\n| heuristic | `ROITELET_ROUTER_long_constant_name_here` |\n"
    )
    code_res = _pp(code_cell)
    # The backtick identifier is copied out byte-for-byte (no injected ZWSP).
    assert "`ROITELET_ROUTER_long_constant_name_here`" in code_res

    math_cell = (
        "| Symbol | Meaning |\n"
        "|---|---|\n"
        "| $\\alpha_{long_subscript_name_here}$ | a long subscripted variable |\n"
    )
    math_res = _pp(math_cell)
    # No ZWSP may land inside the math chunk (would break LaTeX subscripts).
    assert "$\\alpha_{long_subscript_name_here}$" in math_res
    assert "​" not in math_res.split("$")[1]


def test_single_word_column_gets_width_slack() -> None:
    """A single-word (unbreakable) column claims more separator dashes than a
    multi-word column whose cells are the same character length.

    Edge case: the slack heuristic compares *wrap potential* between columns
    of equal width — a delicate numeric property best pinned in isolation
    rather than asserted amid a full table scenario.
    """
    # Both columns are 8 chars wide; column A is unbreakable, column B wraps.
    single = (
        "| A        | B        |\n"
        "|---|---|\n"
        "| abcdefgh | ab cdefg |\n"
        "| ijklmnop | ij klmno |\n"
        "| qrstuvwx | qr stuvw |\n"
    )
    dashes = _separator_dashes(_pp(single))
    assert len(dashes) == 2
    # The unbreakable single-word column earns extra width (more dashes).
    assert dashes[0] > dashes[1], f"expected slack for column A, got {dashes}"

    # When every column wraps, none gets the slack: widths stay equal.
    multi = "| A      | B      |\n|---|---|\n| a a b  | b b c  |\n| c c d  | d d e  |\n"
    even = _separator_dashes(_pp(multi))
    assert even[0] == even[1], f"expected equal widths, got {even}"


def test_html_p_wrapped_img_flattened_to_markdown(tmp_path) -> None:
    """``<p align="center"><img …></p>`` is rewritten as a Markdown image.

    Edge case: the surrounding raw-HTML block would be dropped by Pandoc's
    DOCX writer, so the preprocessor flattens it to a Markdown image. Both
    the ``<p>`` unwrap and the ``<img>``-inside-fence *non*-conversion are
    subtle enough to keep as their own tests.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest temp dir hosting the referenced image and base_dir.
    """
    from PIL import Image as PILImage

    img = tmp_path / "hero.png"
    PILImage.new("RGB", (200, 100), (0, 0, 0)).save(img)
    text = f'<p align="center">\n  <img src="{img.name}" alt="hero shot" width="100%">\n</p>\n'
    result = _pp(text, base_dir=str(tmp_path))
    # The raw HTML is gone; a Markdown image with the alt + width survives.
    assert "<p" not in result and "<img" not in result
    assert f"![hero shot]({img})" in result
    assert "{width=100%}" in result

    # But an <img> shown inside a code fence is example text, not a real ref.
    fenced = _pp('```\n<img src="shown-as-code.png">\n```', base_dir=str(tmp_path))
    assert '<img src="shown-as-code.png">' in fenced


@pytest.mark.skipif(
    not _HAS_SVG_BACKEND,
    reason="needs librsvg (rsvg-convert) or cairosvg installed",
)
def test_svg_rewritten_to_cached_png(tmp_path) -> None:
    """An SVG image (Markdown or raw ``<img>``) is rendered to a cached PNG.

    Edge case: gated on an optional SVG backend, so it must stay skippable on
    its own rather than sinking a whole scenario when the backend is missing.
    Both the Markdown-image and ``<img src>`` entry points are checked.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest temp dir hosting the SVGs and base_dir.
    """
    svg = tmp_path / "logo.svg"
    svg.write_text(
        '<?xml version="1.0"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">'
        '<rect width="100" height="100" fill="red"/></svg>'
    )
    # Markdown-image SVG → cached PNG, source ref rewritten.
    md_res = _pp(f"![logo]({svg.name})", base_dir=str(tmp_path))
    cached_pngs = list(cache_dir("resized").glob("*_max*.png"))
    assert cached_pngs, "expected the SVG rendered into the cache dir"
    assert any(str(p) in md_res for p in cached_pngs)
    assert "logo.svg" not in md_res

    # Raw <img src> pointing at an SVG is rewritten the same way.
    html_res = _pp(f'<img src="{svg.name}" alt="diagram" width="100%">', base_dir=str(tmp_path))
    assert "logo.svg" not in html_res
    assert any(str(p) in html_res for p in cache_dir("resized").glob("*_max*.png"))


def test_isolation_is_idempotent() -> None:
    """Re-running the pipeline must not stack extra blank ``##`` separators.

    Regression guard: the slide-isolation walker used to match only ``"## "``
    (with a trailing space), so it did not recognize the *empty* ``##``
    separator it had itself emitted. A table already preceded by that
    separator then got a second one on every re-run, so ``preprocess_markdown``
    was not a fixed point — the property the md ↔ docx round-trip guarantee
    (see tests/test_roundtrip.py) rests on. Two passes must yield identical
    output.
    """
    text = "## Section\n\nSome intro prose.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n"
    once = _pp(text)
    twice = _pp(once)
    # Fixed-point: the second pass changes nothing.
    assert once == twice
    # And exactly one blank separator was inserted, not a growing pile.
    assert once.count("\n##\n") + once.count("\n## \n") <= 1
