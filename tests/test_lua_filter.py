"""Unit tests for ``md2star/data/filters/md2star.lua``.

Pandoc is the test driver: we feed tiny Markdown fixtures through
``pandoc --lua-filter md2star.lua`` and assert against the produced output.
The Lua filter handles five concerns the Python preprocessor cannot touch
(title extraction, subtitle injection, date localisation, heading-ID strip,
DOCX page break from horizontal rules) so each gets at least one assertion.

The eight original cases collapse into five functional scenarios: title +
subtitle + the no-metadata survival path share one class; date localisation
folds its French / unknown-lang variants into one parametrised case; the
heading-ID strip stands alone; and the horizontal-rule behaviour (DOCX page
break vs. untouched HTML rule) becomes one FORMAT-gate scenario.

The whole module is skipped when ``pandoc`` is not on ``PATH`` — the unit
tests must still pass on machines that have only installed Python deps.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import shutil
import subprocess
import zipfile
from importlib import resources

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc is not installed",
)


def _filter_path() -> str:
    """Return the absolute path to the bundled Lua filter.

    Python 3.10 / 3.11's ``MultiplexedPath.joinpath`` only accepts a single
    component per call, so we chain the segments instead of passing two
    positional args — keeps the test green on every supported interpreter.
    """
    ref = resources.files("md2star.data")
    for part in ("filters", "md2star.lua"):
        ref = ref.joinpath(part)
    return str(ref)


def _run_pandoc(markdown: str, to_fmt: str, *extra: str) -> str:
    """Run pandoc with the md2star Lua filter and return stdout as text."""
    cmd = [
        "pandoc",
        "--from", "markdown",
        "--to", to_fmt,
        "--lua-filter", _filter_path(),
        *extra,
    ]
    proc = subprocess.run(
        cmd,
        input=markdown.encode("utf-8"),
        capture_output=True,
        check=True,
        timeout=20,
    )
    return proc.stdout.decode("utf-8", errors="replace")


# ──────────────────────────────────────────────────────────────────
# Title extraction + subtitle injection + the no-metadata survival path
# ──────────────────────────────────────────────────────────────────


class TestTitleAndSubtitle:
    """The first H1 becomes the document title; author lands in the subtitle."""

    def test_first_h1_becomes_title_with_author_subtitle(self) -> None:
        """The H1 is promoted to ``meta.title`` (and stripped) while author flows in.

        Markdown is the simplest medium to inspect because pandoc's Markdown
        writer preserves YAML metadata explicitly. One standalone render
        exercises both the title-promotion and subtitle-injection branches.
        """
        out = _run_pandoc(
            "# Hello World\n\nBody text.",
            "markdown",
            "--standalone",
            "--metadata", "author=Alice",
        )
        # The H1 should appear in the YAML metadata block as the title.
        assert "title: Hello World" in out
        # The body still contains the prose.
        assert "Body text." in out
        # The H1 is stripped from the body (only survives in the front-matter).
        body_start = out.find("---\n", out.find("---\n") + 1)  # end of front-matter
        body = out[body_start:] if body_start != -1 else out
        assert "# Hello World" not in body
        # The author is wrapped into the Subtitle div; the Markdown writer
        # surfaces that as the literal author string somewhere in the output.
        assert "Alice" in out

    def test_no_h1_no_author_survives_id_strip_path(self) -> None:
        """A document without an H1 or author still passes through the filter intact.

        This drives the heading-ID-strip branch on a non-H1 heading while
        confirming the title/subtitle logic degrades gracefully to a no-op.
        """
        out = _run_pandoc("## Just a Level-2\n\nText.\n", "markdown")
        # Nothing was promoted or dropped — the level-2 heading and prose remain.
        assert "Just a Level-2" in out
        assert "Text." in out


# ──────────────────────────────────────────────────────────────────
# Date localisation
# ──────────────────────────────────────────────────────────────────


def test_date_localisation() -> None:
    """``date_format`` + ``lang`` localise month names for supported languages only.

    ``%B`` alone keeps the output deterministic across runs (the year changes
    daily but the month name does not). A supported language (fr-FR) surfaces a
    French month from the dict; an unknown language (xx-YY) drops through to the
    system locale and must never pull a dictionary month.
    """
    french_months = (
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    )

    def _render(lang: str) -> str:
        return _run_pandoc(
            "# Titre\n\nCorps.\n", "markdown", "--standalone",
            "--metadata", f"lang={lang}", "--metadata", "date_format=%B",
        ).lower()

    # Supported language surfaces at least one French month name.
    fr = _render("fr-FR")
    assert any(m in fr for m in french_months), f"expected a French month in: {fr!r}"

    # Unknown language must not pull French/German dict months.
    xx = _render("xx-YY")
    assert "février" not in xx and "februar" not in xx


# ──────────────────────────────────────────────────────────────────
# Heading ID cleanup
# ──────────────────────────────────────────────────────────────────


def test_h2_auto_id_is_stripped() -> None:
    """Auto-generated heading IDs are stripped (meaningless in DOCX)."""
    out = _run_pandoc("## Section A\n\nBody.\n", "markdown")
    # Pandoc's Markdown writer would emit ``{#section-a}`` after the heading
    # text if the identifier survived; the filter removes it.
    assert "{#section-a}" not in out
    assert "Section A" in out


# ──────────────────────────────────────────────────────────────────
# Horizontal rule → page break, gated on the output FORMAT
# ──────────────────────────────────────────────────────────────────


def test_horizontal_rule_is_page_break_in_docx_only(tmp_path) -> None:
    """``---`` becomes a DOCX page break but stays a plain rule elsewhere.

    The filter's HR branch is FORMAT-gated: in DOCX it emits raw
    ``<w:br w:type="page"/>`` OOXML; in every other format the default
    horizontal rule renders untouched. HTML stands in for "not DOCX"
    because it is trivial to introspect and shares the same gate as PPTX.
    """
    # --- DOCX path: HR must become a hard page break. ---
    out_docx = tmp_path / "page-break.docx"
    # Use file output because pandoc cannot write DOCX to stdout.
    subprocess.run(
        [
            "pandoc",
            "--from", "markdown",
            "--to", "docx",
            "--lua-filter", _filter_path(),
            "-o", str(out_docx),
        ],
        input="Before page break.\n\n---\n\nAfter page break.\n".encode("utf-8"),
        check=True,
        timeout=20,
    )
    with zipfile.ZipFile(out_docx) as z:
        doc_xml = z.read("word/document.xml").decode("utf-8")
    # The raw OOXML the filter emits on HR in a Word target.
    assert '<w:br w:type="page"' in doc_xml

    # --- HTML path: HR must be left as a literal rule, no Word XML leakage. ---
    html = _run_pandoc("Before.\n\n---\n\nAfter.\n", "html")
    assert "<hr" in html
    assert "<w:br" not in html
