"""Unit tests for ``md2star/data/filters/md2star.lua``.

Pandoc is the test driver: we feed tiny Markdown fixtures through
``pandoc --lua-filter md2star.lua`` and assert against the produced output.
The Lua filter handles five concerns the Python preprocessor cannot touch
(title extraction, subtitle injection, date localisation, heading-ID strip,
DOCX page break from horizontal rules) so each gets at least one assertion.

The whole module is skipped when ``pandoc`` is not on ``PATH`` — the unit
tests must still pass on machines that have only installed Python deps.
"""

from __future__ import annotations

import shutil
import subprocess
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
# Title extraction + subtitle injection
# ──────────────────────────────────────────────────────────────────


class TestTitleAndSubtitle:
    """The first H1 becomes the document title; author + date land in subtitle."""

    def test_first_h1_becomes_title(self) -> None:
        """A standalone H1 is promoted to ``meta.title`` and stripped from the body."""
        # Markdown output is the simplest medium to inspect because pandoc's
        # Markdown writer preserves YAML metadata explicitly.
        out = _run_pandoc("# Hello World\n\nBody text.", "markdown", "--standalone")
        # The H1 should appear in the YAML metadata block, not as a body heading.
        assert "title: Hello World" in out
        # The body should still contain the prose but not the H1 line.
        assert "Body text." in out
        # We accept either "# Hello World" entirely absent OR present only as
        # part of the metadata serialization — check the body specifically.
        body_start = out.find("---\n", out.find("---\n") + 1)  # end of front-matter
        body = out[body_start:] if body_start != -1 else out
        assert "# Hello World" not in body

    def test_subtitle_holds_author_when_provided(self) -> None:
        """``--metadata author=...`` flows into the subtitle div."""
        out = _run_pandoc(
            "# Doc\n\nBody.\n",
            "markdown",
            "--standalone",
            "--metadata", "author=Alice",
        )
        # The Lua filter wraps the author into a Div with custom-style="Subtitle".
        # In the Markdown writer that surfaces as the literal author string.
        assert "Alice" in out

    def test_no_author_no_h1_only_id_strip(self) -> None:
        """A document without an H1 or author still survives the filter."""
        out = _run_pandoc("## Just a Level-2\n\nText.\n", "markdown")
        assert "Just a Level-2" in out
        assert "Text." in out


# ──────────────────────────────────────────────────────────────────
# Date localisation
# ──────────────────────────────────────────────────────────────────


class TestDateLocalisation:
    """``date_format`` + ``lang`` produce localised month / weekday names."""

    def test_french_month_name_injected(self) -> None:
        """``lang: fr-FR`` + ``%B`` substitutes a French month name."""
        # %B alone keeps the output deterministic across runs (the year
        # changes daily but the month name does not).
        out = _run_pandoc(
            "# Titre\n\nCorps.\n",
            "markdown",
            "--standalone",
            "--metadata", "lang=fr-FR",
            "--metadata", "date_format=%B",
        )
        french_months = (
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        )
        assert any(m.lower() in out.lower() for m in french_months), (
            f"expected a French month name in: {out!r}"
        )

    def test_english_fallback_when_lang_unknown(self) -> None:
        """An unknown ``lang`` falls back to the system locale (English-ish)."""
        # The filter only carries dictionaries for 7 languages; anything else
        # gets the raw ``%B`` from os.date(), which on en_* locales is English.
        out = _run_pandoc(
            "# Doc\n\nBody.\n",
            "markdown",
            "--standalone",
            "--metadata", "lang=xx-YY",
            "--metadata", "date_format=%B",
        )
        # Should not contain a French / German month name from the dict.
        assert "février" not in out.lower()
        assert "februar" not in out.lower()


# ──────────────────────────────────────────────────────────────────
# Heading ID cleanup
# ──────────────────────────────────────────────────────────────────


class TestHeadingIdStrip:
    """Auto-generated heading IDs are stripped (meaningless in DOCX)."""

    def test_h2_id_removed(self) -> None:
        """``## My Heading {#my-heading}`` loses the identifier."""
        out = _run_pandoc("## Section A\n\nBody.\n", "markdown")
        # Pandoc's Markdown writer would emit ``{#section-a}`` after the
        # heading text if the identifier were present. The filter strips it.
        assert "{#section-a}" not in out
        assert "Section A" in out


# ──────────────────────────────────────────────────────────────────
# Horizontal rule → page break (DOCX only)
# ──────────────────────────────────────────────────────────────────


class TestPageBreak:
    """``---`` becomes a hard page break in DOCX output."""

    def test_hr_emits_page_break_in_docx(self, tmp_path) -> None:
        """The DOCX path should contain a ``<w:br w:type="page"/>`` element."""
        import zipfile

        out_docx = tmp_path / "page-break.docx"
        # Use the file-output path because pandoc cannot write DOCX to stdout.
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
        # The raw OOXML emitted by the filter on HR.
        assert '<w:br w:type="page"' in doc_xml

    def test_hr_preserved_in_pptx_path(self, tmp_path) -> None:
        """Other output formats keep the default horizontal-rule rendering."""
        # We use HTML rather than PPTX because PPTX is harder to introspect
        # and the filter's HR branch is FORMAT-gated identically for both.
        out = _run_pandoc(
            "Before.\n\n---\n\nAfter.\n",
            "html",
        )
        # HTML emits a literal <hr>; the filter must not have replaced it.
        assert "<hr" in out
        # And critically, no Word page-break XML leaked into HTML output.
        assert '<w:br' not in out
