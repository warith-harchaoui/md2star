"""Run-to-run determinism of md2star conversions (the honest "idempotence").

The README promises a "stable fixed point"; ``test_roundtrip.py`` proves the
*semantic* form (md → docx → md converges). This module proves a stricter,
different property: **converting the same source twice yields text-identical
output**. Two independent runs must not drift because of dict-iteration order,
uninitialised state, or any hidden nondeterminism in the pipeline.

Normalization decision
-----------------------
DOCX/PPTX/PDF are binary containers that embed timestamps and UUIDs, so
byte-identity is unattainable and *not* the target. We instead pin the one
intentional per-run variation — the injected date subtitle — with a fixed
``--date`` and compare the **extracted text** of two runs:

* DOCX → Pandoc's native reader (``-t gfm``).
* PPTX → the ``<a:t>`` text runs pulled straight from the slide XML (no extra
  dependency; Pandoc cannot read PPTX back in).
* PDF  → kreuzberg text extraction (``slow``; needs LibreOffice + kreuzberg).

If two runs disagree on extracted text, the pipeline is nondeterministic and
this test fails — which is exactly the regression signal the goal asked for.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

# The whole module needs Pandoc (the docx/pptx generator). Pinning the date
# removes md2star's only intentional per-run variation, so any remaining
# difference between two runs is a genuine determinism bug.
pytestmark = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")

_FIXED_DATE = "2026-01-01"

# A fixture rich enough to expose ordering-sensitive drift: multiple headings,
# every emphasis kind, a table, and a multi-item list (list/table iteration is
# where nondeterministic dict/set ordering would most likely surface).
_SRC = """\
# Determinism Check

Intro paragraph with **bold**, *italic*, and `code`.

## Metrics

| Metric  | Before | After  |
|---------|--------|--------|
| Latency | 320 ms | 190 ms |
| Uptime  | 99.1   | 99.8   |

## Items

- First action item.
- Second action item.
- Third action item.
"""


def _convert(fmt: str, tmp_path: Path, tag: str) -> Path:
    """Convert :data:`_SRC` to *fmt* with a pinned date. Returns the output path."""
    from md2star.cli import _convert as convert

    # One source file, two distinct outputs (tag a / b) so the two runs cannot
    # accidentally share state through the filesystem.
    src = tmp_path / "src.md"
    if not src.exists():
        src.write_text(_SRC, encoding="utf-8")
    out = tmp_path / f"{tag}.{fmt}"
    rc = convert(fmt, [str(src), "-o", str(out), "--offline", "--date", _FIXED_DATE])
    assert rc == 0, f"md2{fmt} failed (rc={rc})"
    return out


def _docx_text(path: Path) -> str:
    """Extract DOCX text via Pandoc's native reader, trailing space stripped."""
    proc = subprocess.run(
        ["pandoc", str(path), "-t", "gfm", "--wrap=none"],
        capture_output=True, check=True, timeout=30,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    # Drop trailing whitespace/blank lines — cosmetic render artefacts, never
    # a determinism signal.
    return "\n".join(ln.rstrip() for ln in text.splitlines() if ln.strip())


def _pptx_text(path: Path) -> str:
    """Extract PPTX text from the slide XML ``<a:t>`` runs, slide order fixed.

    Pandoc has no PPTX reader, so we read the OOXML directly: concatenate every
    text run, per slide, with slides sorted by name for a stable ordering.
    """
    out: list[str] = []
    with zipfile.ZipFile(path) as zf:
        # ``ppt/slides/slideN.xml`` — sort by the numeric N so slide 10 does not
        # sort before slide 2 (plain string sort would misorder).
        slides = sorted(
            (n for n in zf.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
            key=lambda n: int(re.search(r"(\d+)", n).group(1)),
        )
        for name in slides:
            xml = zf.read(name).decode("utf-8", errors="replace")
            # ``<a:t>`` holds the visible text of each run; that is all we compare.
            out.extend(re.findall(r"<a:t>(.*?)</a:t>", xml, re.DOTALL))
    return "\n".join(out)


def test_docx_conversion_is_run_to_run_stable(tmp_path) -> None:
    """Two DOCX conversions of the same source extract to identical text."""
    a = _docx_text(_convert("docx", tmp_path, "a"))
    b = _docx_text(_convert("docx", tmp_path, "b"))
    assert a == b, "DOCX text drifted between two runs of the same input"
    # Guard against a vacuous pass: the extraction must have found real content.
    assert "Latency" in a and "action item" in a


def test_pptx_conversion_is_run_to_run_stable(tmp_path) -> None:
    """Two PPTX conversions of the same source extract to identical text."""
    a = _pptx_text(_convert("pptx", tmp_path, "a"))
    b = _pptx_text(_convert("pptx", tmp_path, "b"))
    assert a == b, "PPTX text drifted between two runs of the same input"
    assert "Latency" in a and "action item" in a


@pytest.mark.slow
@pytest.mark.skipif(
    shutil.which("soffice") is None or importlib.util.find_spec("kreuzberg") is None,
    reason="PDF idempotence needs LibreOffice (soffice) + kreuzberg",
)
def test_pdf_conversion_is_run_to_run_stable(tmp_path) -> None:
    """Two PDF conversions of the same source extract to identical text."""
    from kreuzberg import ExtractionConfig, OutputFormat, extract_file_sync

    cfg = ExtractionConfig(output_format=OutputFormat.PLAIN)

    def _pdf_text(p: Path) -> str:
        raw = extract_file_sync(str(p), config=cfg).content
        return "\n".join(ln.rstrip() for ln in raw.splitlines() if ln.strip())

    a = _pdf_text(_convert("pdf", tmp_path, "a"))
    b = _pdf_text(_convert("pdf", tmp_path, "b"))
    assert a == b, "PDF text drifted between two runs of the same input"
    assert "Latency" in a
