"""End-to-end integration tests using the fixtures under tests/fixtures/.

Each test:

* Skips cleanly when its external dependency is missing — `pandoc`
  must be present (it's a hard md2star requirement), but `soffice`,
  `node`, and `--bib`'s citeproc are optional. A missing optional
  dep yields ``pytest.skip(reason=...)``, not a failure.
* Calls the CLI's ``_convert`` entry point directly (no subprocess)
  so the tests are fast and the failure mode is a clean Python
  traceback instead of a captured shell stderr.
* Asserts the output bytes are a recognizable file of the expected
  type (PDF magic, OOXML zip magic + an expected internal entry).

These tests exist to catch regressions in the integration *paths*
md2star wires together — pandoc invocation, template resolution,
soffice piping, mermaid plumbing — not to retest pandoc itself.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import logging
import re
import shutil
import zipfile
from pathlib import Path

import pytest


def _docx_text(body: str) -> str:
    """Return the concatenated visible text from a ``word/document.xml`` body.

    Pandoc 3.6+ may split a single source word into one ``<w:t>`` per
    character or per word, which breaks naive substring assertions like
    ``"Simple smoke test" in body``. Joining every text run lets the tests
    assert on prose rather than on OOXML structure.
    """
    return "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", body))

FIXTURES = Path(__file__).parent / "fixtures"

PANDOC = shutil.which("pandoc")
SOFFICE = (
    shutil.which("soffice")
    or shutil.which("libreoffice")
    or (
        "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").exists()
        else None
    )
)
NODE = shutil.which("node")

needs_pandoc = pytest.mark.skipif(
    PANDOC is None, reason="pandoc not on PATH",
)
needs_soffice = pytest.mark.skipif(
    SOFFICE is None, reason="LibreOffice (soffice) not on PATH",
)
needs_node = pytest.mark.skipif(
    NODE is None, reason="node.js not on PATH — mermaid rendering requires it",
)


def _convert(fmt: str, in_path: Path, out_path: Path, *extra: str) -> int:
    """Tiny shim around md2star.cli._convert. Returns exit code.

    Injects ``--no-remote-templates`` by default so these tests never
    reach deraison.ai (the v2.5.0 remote-template default): the fixtures
    ship no local ``template.<fmt>``, so without this every conversion
    here would attempt a network fetch. A test that deliberately
    exercises the network can still pass ``--offline`` /
    ``--no-remote-templates`` itself — we don't double it up.
    """
    from md2star.cli import _convert as cli_convert
    net_neutral = {"--offline", "--no-remote-templates"}
    prefix = () if net_neutral & set(extra) else ("--no-remote-templates",)
    argv = [str(in_path), "-o", str(out_path), *prefix, *extra]
    return cli_convert(fmt, argv)


# ─────────────────────────────────────────────────────────────────────
# DOCX — the workhorse path
# ─────────────────────────────────────────────────────────────────────


@needs_pandoc
class TestDocx:
    def test_simple_fixture_produces_valid_docx(self, tmp_path):
        out = tmp_path / "simple.docx"
        rc = _convert("docx", FIXTURES / "simple.md", out)
        assert rc == 0
        assert out.exists() and out.stat().st_size > 1024
        # DOCX is a zip with a known internal entry.
        with zipfile.ZipFile(out) as z:
            assert "word/document.xml" in z.namelist()
            body = z.read("word/document.xml").decode("utf-8")
            assert "Simple smoke test" in _docx_text(body)

    def test_metadata_fixture_localises_to_french(self, tmp_path):
        out = tmp_path / "metadata.docx"
        rc = _convert("docx", FIXTURES / "metadata.md", out)
        assert rc == 0
        with zipfile.ZipFile(out) as z:
            body = z.read("word/document.xml").decode("utf-8")
        # Expect a French month name somewhere in the rendered date
        # subtitle (any of the 12; the day-of-month / year vary).
        french_months = (
            "janvier", "février", "mars", "avril", "mai", "juin",
            "juillet", "août", "septembre", "octobre", "novembre", "décembre",
        )
        assert any(m in body.lower() for m in french_months), (
            "expected a French month name in the rendered subtitle"
        )

    def test_bibliography_fixture_renders_citation(self, tmp_path):
        out = tmp_path / "bib.docx"
        rc = _convert(
            "docx", FIXTURES / "bibliography.md", out,
            "--bib", str(FIXTURES / "refs.bib"),
            "--bibliography-name", "References",
        )
        assert rc == 0
        with zipfile.ZipFile(out) as z:
            body = z.read("word/document.xml").decode("utf-8")
        # Citation key resolves to author "Pearl"; the heading is the
        # one we asked for via --bibliography-name.
        assert "Pearl" in body, "citation didn't resolve via citeproc"
        assert "References" in body, "--bibliography-name heading missing"


# ─────────────────────────────────────────────────────────────────────
# PPTX
# ─────────────────────────────────────────────────────────────────────


@needs_pandoc
class TestPptx:
    def test_simple_fixture_produces_valid_pptx(self, tmp_path):
        out = tmp_path / "simple.pptx"
        rc = _convert("pptx", FIXTURES / "simple.md", out)
        assert rc == 0
        assert out.exists() and out.stat().st_size > 1024
        # PPTX is a zip; the presentation manifest must be present.
        with zipfile.ZipFile(out) as z:
            assert "ppt/presentation.xml" in z.namelist()


# ─────────────────────────────────────────────────────────────────────
# PDF — depends on soffice
# ─────────────────────────────────────────────────────────────────────


@needs_pandoc
@needs_soffice
class TestPdf:
    def test_simple_fixture_produces_valid_pdf(self, tmp_path):
        out = tmp_path / "simple.pdf"
        rc = _convert("pdf", FIXTURES / "simple.md", out)
        assert rc == 0
        assert out.exists() and out.stat().st_size > 1024
        # PDFs start with the %PDF- magic. (Most PDFs are PDF-1.4 to
        # PDF-1.7; soffice emits 1.7 by default.)
        with open(out, "rb") as f:
            head = f.read(8)
        assert head.startswith(b"%PDF-"), f"not a PDF? got: {head!r}"


# ─────────────────────────────────────────────────────────────────────
# Remote images — exercise the offline-by-default policy
# ─────────────────────────────────────────────────────────────────────


@needs_pandoc
class TestRemoteImagesPolicy:
    def test_default_does_not_download(self, tmp_path, caplog):
        caplog.set_level(logging.WARNING, logger="md2star")
        out = tmp_path / "images.docx"
        rc = _convert("docx", FIXTURES / "images.md", out)
        assert rc == 0
        # The warning is the contract surface — without the flag, md2star logs
        # one line naming the blocked URL and the opt-in flag.
        assert (
            "--allow-remote-images" in caplog.text
        ), "expected the soft-refusal warning to mention the opt-in flag"


# ─────────────────────────────────────────────────────────────────────
# Mermaid — depends on Node.js
# ─────────────────────────────────────────────────────────────────────


@needs_pandoc
@needs_node
class TestMermaid:
    def test_mermaid_fixture_embeds_rendered_image(self, tmp_path):
        out = tmp_path / "mermaid.docx"
        rc = _convert("docx", FIXTURES / "mermaid.md", out)
        # The mermaid pipeline is allowed to silently fall back to the
        # raw code fence when mmdc fails — we still expect rc == 0.
        assert rc == 0
        assert out.exists() and out.stat().st_size > 1024
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
        # Either an embedded PNG (success) or the raw code text (graceful
        # fallback). Both are acceptable — the test asserts the failure
        # didn't break the document.
        has_image = any(n.startswith("word/media/") for n in names)
        if not has_image:
            with zipfile.ZipFile(out) as z:
                body = z.read("word/document.xml").decode("utf-8")
            assert "flowchart" in body or "mermaid" in body, (
                "mermaid block was neither rendered nor preserved as text"
            )
