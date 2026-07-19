"""Round-trip fidelity: ``md → docx → md`` recovers the source content.

md2star's promise is that its DOCX output is a *faithful, reversible*
rendering of your Markdown — not a one-way dead end. This module proves it
by converting a Markdown fixture to DOCX (via the real CLI path) and reading
it straight back with Pandoc's native DOCX reader, then checking two things:

1. **Content survival** — every heading, list item, table cell, and the
   ``**bold**`` / ``*italic*`` / `` `code` `` emphasis of the source appears
   in the recovered Markdown.
2. **Fixed point** — the pipeline is idempotent in the mathematical sense:
   running it twice yields the same document as running it once
   (``g(g(x)) == g(x)``), so repeated conversions converge instead of
   drifting. The one element md2star *adds* by design — a localized date
   subtitle re-stamped on every run — is normalized out before the
   comparison (see :func:`_canon`); nothing else may change.

Pandoc is the reverse reader because it is already a hard md2star dependency
(no new package), reads DOCX natively, and preserves inline code spans. The
harder ``pdf → text`` OCR direction — the strict ``g(f(x)) = x`` identity through
a *printed* PDF read back with ``kreuzberg`` — is validated **in-tree** by
:mod:`tests.test_roundtrip_ocr` (marked ``slow``; it runs whenever LibreOffice
and kreuzberg are installed, and CI installs them so it actually executes).

The whole module skips when ``pandoc`` is not on ``PATH`` — mirroring
``tests/test_lua_filter.py`` so the pure-Python test set still passes on a
machine with only the pip deps installed.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import re
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc is not installed",
)

# A date-shaped H1 (localized long form, e.g. "# Sunday, July 5, 2026" or
# "# 5 juillet 2026"). md2star injects one such subtitle on every run; when a
# recovered document is re-converted it picks up a fresh one, so we strip all
# of them before the fixed-point comparison. This is the *only* content
# md2star adds that is not present in the source.
_DATE_H1 = re.compile(
    r"^#\s+(?:\w+,\s+\w+\s+\d{1,2},\s+\d{4}"     # English: Sunday, July 5, 2026
    r"|\d{1,2}\s+\w+\s+\d{4})\s*$",              # French:  5 juillet 2026
    re.MULTILINE,
)


def _md_to_docx(md_text: str, tmp_path, tag: str):
    """Convert Markdown text to a DOCX via the real CLI path. Returns the path."""
    from md2star.cli import _convert

    src = tmp_path / f"{tag}.md"
    out = tmp_path / f"{tag}.docx"
    src.write_text(md_text, encoding="utf-8")
    rc = _convert("docx", [str(src), "-o", str(out), "--offline"])
    assert rc == 0, f"md2docx failed on {tag} (rc={rc})"
    return out


def _docx_to_md(docx_path) -> str:
    """Read a DOCX back to GitHub-flavored Markdown with Pandoc's native reader."""
    proc = subprocess.run(
        ["pandoc", str(docx_path), "-t", "gfm", "--wrap=none"],
        capture_output=True,
        check=True,
        timeout=30,
    )
    return proc.stdout.decode("utf-8", errors="replace")


def _roundtrip(md_text: str, tmp_path, tag: str) -> str:
    """One application of the round-trip: md text → docx → md text."""
    return _docx_to_md(_md_to_docx(md_text, tmp_path, tag))


def _canon(md: str) -> str:
    """Normalize the differences that are cosmetic or added-by-design.

    - Drop every md2star-injected date subtitle (the sole intentional
      addition; see :data:`_DATE_H1`).
    - Collapse pipe-table separator dash runs (``|-----|`` ≡ ``|---|``; the
      dash count is a width *hint*, not content).
    - Strip trailing whitespace and blank lines (line wrapping and vertical
      spacing never survive a DOCX render and carry no meaning).
    """
    md = _DATE_H1.sub("", md)
    md = re.sub(r"\|[\s:-]+\|", lambda m: re.sub(r"-+", "---", m.group(0)), md)
    return "\n".join(ln.rstrip() for ln in md.splitlines() if ln.strip())


# A fixture that exercises the constructs a round-trip must preserve:
# headings at two levels, an intro paragraph with all three emphasis kinds,
# a pipe table, and a bullet list.
_RICH_MD = """\
# Quarterly Engineering Report

This paragraph carries **bold**, *italic*, and `code` emphasis that a
faithful round-trip must preserve verbatim.

## Key Metrics

| Metric  | Before | After  |
|---------|--------|--------|
| Latency | 320 ms | 190 ms |
| Uptime  | 99.1   | 99.8   |

## Action Items

- Consolidate the Redis clusters before September.
- Migrate the Payments queue to the new broker.
"""


def test_content_survives_the_roundtrip(tmp_path):
    """Every heading, emphasis span, table cell, and list item comes back."""
    recovered = _roundtrip(_RICH_MD, tmp_path, "rich")

    # Headings (the H1 title may migrate into DOCX metadata rather than a body
    # heading, so we assert on the H2 section headings that stay in the body).
    assert "Key Metrics" in recovered
    assert "Action Items" in recovered

    # Emphasis: all three kinds survive as Markdown syntax.
    assert "**bold**" in recovered
    assert "*italic*" in recovered
    assert "`code`" in recovered

    # Table cells.
    for cell in ("Metric", "Latency", "320 ms", "190 ms", "Uptime", "99.8"):
        assert cell in recovered, f"table cell {cell!r} lost in round-trip"

    # List items.
    assert "Consolidate the Redis clusters before September." in recovered
    assert "Migrate the Payments queue to the new broker." in recovered


def test_roundtrip_reaches_a_fixed_point(tmp_path):
    """``g(g(x)) == g(x)`` — a second pass changes nothing (modulo the date)."""
    once = _roundtrip(_RICH_MD, tmp_path, "once")
    twice = _roundtrip(once, tmp_path, "twice")
    assert _canon(once) == _canon(twice)


def test_fixed_point_for_varied_documents(tmp_path):
    """The fixed-point property holds across paragraph / list / table / section docs.

    Each source keeps a paragraph before the table/list because Pandoc migrates a
    lone ``# Title`` into the DOCX title *metadata*; a body that is only a bare
    table then needs one extra pass to settle. Real documents have prose, and
    those are an immediate fixed point.
    """
    sources = [
        "# Title\n\nA single paragraph of prose with no other structure.\n",
        "# Heading\n\nIntro line before the list.\n\n- one\n- two\n- three\n",
        "# Doc\n\nIntro line before the table.\n\n| A | B |\n|---|---|\n| 1 | 2 |\n",
        "# Doc\n\nIntro.\n\n## Section\n\nBody under a section heading.\n",
    ]
    for i, source in enumerate(sources):
        once = _roundtrip(source, tmp_path, f"a{i}")
        twice = _roundtrip(once, tmp_path, f"b{i}")
        assert _canon(once) == _canon(twice)
