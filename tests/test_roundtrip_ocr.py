"""OCR round-trip fidelity: ``md → docx → pdf → (kreuzberg) → text`` survives.

This is the *long* arm of the idempotence story. :mod:`tests.test_roundtrip`
proves the cheap, dependency-free direction (``md → docx → md`` via Pandoc's
native reader). This module proves the expensive one that mirrors what a real
downstream reader does to a *printed* document: render the Markdown all the way
to a PDF through md2star's real CLI path (LibreOffice under the hood), then pull
the text back out with `kreuzberg <https://github.com/Goldziher/kreuzberg>`_ —
the same OCR / text-extraction engine a consumer would use on a PDF they were
handed.

Why content-survival rather than a strict fixed point
-----------------------------------------------------
A PDF has no Markdown layer: bold/italic/`code` emphasis, table pipes, and list
bullets are *rendered*, not stored, so they cannot come back as Markdown tokens.
And md2star injects a localized date subtitle on every run by design. So the
contract we can honestly assert here is **content survival** — every heading's
text, every list item, and the substantive words of every paragraph reappear in
the extracted text — not byte-for-byte idempotence. The strict ``g(g(x)) ==
g(x)`` fixed point lives in :mod:`tests.test_roundtrip`; this module guards the
weaker-but-broader promise that nothing a reader *cares about* is lost on the way
to PDF.

Why kreuzberg is a test-only dependency
---------------------------------------
kreuzberg is heavy (OCR stack) and only exercises the *verification* direction —
it is never part of md2star's normal ``md → docx/pptx/pdf`` runtime. So it lives
in the ``dev`` extra, and the whole module skips cleanly when kreuzberg (or
LibreOffice, or Pandoc) is absent, mirroring :mod:`tests.test_roundtrip`. It is
marked ``slow`` because a LibreOffice render plus a kreuzberg pass costs seconds,
not milliseconds; the fast suite stays fast.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

# Every leg of this chain has an external prerequisite, and any one of them being
# absent makes the whole test meaningless rather than failing. Gate on all three
# up front so the module skips as a unit on a bare machine:
#   - pandoc   : md2star's Markdown reader (the very first hop);
#   - soffice  : headless LibreOffice, how md2star renders DOCX → PDF;
#   - kreuzberg: the text/OCR extractor that reads the PDF back.
_HAS_PANDOC = shutil.which("pandoc") is not None
_HAS_SOFFICE = shutil.which("soffice") is not None or shutil.which("libreoffice") is not None
_HAS_KREUZBERG = importlib.util.find_spec("kreuzberg") is not None

# Two class-level markers: skip unless the full toolchain is present, and tag the
# module ``slow`` so ``pytest -m "not slow"`` keeps the millisecond suite lean.
pytestmark = [
    pytest.mark.skipif(
        not (_HAS_PANDOC and _HAS_SOFFICE and _HAS_KREUZBERG),
        reason="requires pandoc + libreoffice (soffice) + kreuzberg",
    ),
    pytest.mark.slow,
]


def _md_to_pdf(md_text: str, tmp_path: Path, tag: str) -> Path:
    """Render Markdown text to a PDF through md2star's real CLI path.

    Parameters
    ----------
    md_text : str
        The Markdown source to convert.
    tmp_path : pathlib.Path
        Pytest's per-test temporary directory; holds the ``.md`` input and
        the ``.pdf`` output.
    tag : str
        Short slug used to name the intermediate files uniquely within a test.

    Returns
    -------
    pathlib.Path
        Path to the freshly written PDF.
    """
    # Reuse the exact entry point the CLI uses (not a subprocess) so the test
    # exercises the same code the ``md2pdf`` command runs. ``--offline`` keeps
    # the conversion from touching the network, matching test_roundtrip.
    from md2star.cli import _convert

    src = tmp_path / f"{tag}.md"
    out = tmp_path / f"{tag}.pdf"
    src.write_text(md_text, encoding="utf-8")
    rc = _convert("pdf", [str(src), "-o", str(out), "--offline"])

    # A non-zero return code means LibreOffice failed to render; surface the tag
    # so a CI failure points at the offending fixture immediately.
    assert rc == 0, f"md2pdf failed on {tag} (rc={rc})"
    return out


def _pdf_to_text(pdf_path: Path) -> str:
    """Extract the text layer of a PDF with kreuzberg (the reverse reader).

    Parameters
    ----------
    pdf_path : pathlib.Path
        The PDF produced by :func:`_md_to_pdf`.

    Returns
    -------
    str
        The document's recovered plain text. Emphasis, table borders, and
        bullet glyphs are gone — only textual content survives a PDF render.
    """
    # Imported lazily: the module-level skip guarantees kreuzberg is present by
    # the time any test body runs, so the import never fails here.
    from kreuzberg import extract_file_sync

    # extract_file_sync returns an ExtractionResult; ``.content`` is the flat
    # text we compare against. kreuzberg auto-detects the PDF handler.
    result = extract_file_sync(str(pdf_path))
    return result.content


# A fixture chosen so every survivor is an unambiguous, PDF-safe token: distinct
# heading words, list items with unique nouns, and a paragraph sentence. No
# reliance on **bold**/*italic*/`code` — those are rendered away by design and
# are already covered by the Markdown-level round-trip test.
_OCR_MD = """\
# Idempotence Probe

## Section One

This paragraph anchors the first section with the word Kreuzberg.

- Alpha consolidation task
- Beta migration task
- Gamma cleanup task

## Section Two

The closing paragraph mentions Payments and Latency explicitly.
"""

# The tokens that MUST survive md → pdf → text. Each is a plain word or short
# phrase with no Markdown syntax, so extraction — OCR or text-layer — recovers
# it verbatim. Emphasis markers and the injected date subtitle are deliberately
# excluded (they are not part of the survival contract; see the module docstring).
_EXPECTED_TOKENS = [
    "Idempotence Probe",       # H1 title text
    "Section One",             # H2 heading
    "Section Two",             # H2 heading
    "Kreuzberg",               # word inside the first paragraph
    "Alpha consolidation task",  # list item 1
    "Beta migration task",       # list item 2
    "Gamma cleanup task",        # list item 3
    "Payments",                # noun in the closing paragraph
    "Latency",                 # noun in the closing paragraph
]


def test_content_survives_the_ocr_roundtrip(tmp_path: Path) -> None:
    """Every heading, list item, and paragraph noun returns through the PDF.

    This is the end-to-end assertion: push the fixture all the way to PDF via
    the real md2pdf path, read it back with kreuzberg, and confirm each token
    that carries meaning reappears. Formatting is intentionally not checked.
    """
    # One full pass through the expensive chain.
    pdf = _md_to_pdf(_OCR_MD, tmp_path, "ocr")
    recovered = _pdf_to_text(pdf)

    # Assert token-by-token so a failure names exactly what was dropped rather
    # than dumping the whole extracted blob.
    for token in _EXPECTED_TOKENS:
        assert token in recovered, f"{token!r} did not survive md → pdf → text"


def test_ocr_roundtrip_is_stable_across_two_renders(tmp_path: Path) -> None:
    """Rendering twice recovers the same content set — no cumulative drift.

    True byte-level idempotence is impossible once a document has been through
    a PDF (no Markdown layer to compare, plus the re-stamped date subtitle). The
    honest stability claim is that the *set of surviving tokens* is invariant:
    a second render loses nothing the first one kept.
    """
    # Render the same source twice into separate files.
    first = _pdf_to_text(_md_to_pdf(_OCR_MD, tmp_path, "ocr_a"))
    second = _pdf_to_text(_md_to_pdf(_OCR_MD, tmp_path, "ocr_b"))

    # Every contract token present after the first render is present after the
    # second; the survival set does not shrink run over run.
    for token in _EXPECTED_TOKENS:
        assert (token in first) == (token in second), (
            f"{token!r} survived one render but not the other — the OCR "
            "round-trip is not stable"
        )
