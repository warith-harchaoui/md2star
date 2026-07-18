"""OCR round-trip identity: ``g(f(x)) = x`` for md2star's ``md → pdf → text`` pipeline.

Precise statement
-----------------
Define three maps:

* ``f : Markdown → PDF`` — md2star's forward renderer (``md → docx → pdf``, with
  LibreOffice doing the DOCX→PDF step). This is exactly what the ``md2pdf`` CLI runs.
* ``g : PDF → text`` — the reverse reader: kreuzberg's PDF text extraction with
  ``OutputFormat.PLAIN``, which preserves line and list structure (unlike the
  MARKDOWN format, which merges list items onto one line and drops the space at
  wrap points).
* ``N : text → text`` — a canonical *normal form* (see :func:`_normal_form`).

This module proves the **reversibility identity**

.. math::  N(g(f(x))) = N(x) \\quad\\text{for every } x \\in D,

i.e. ``g ∘ f`` is the identity on Markdown *up to the normal form* ``N``. This is
the strict claim ``g(f(x)) = x`` (not a hand-waved "content survives", and not the
weaker ``g(g(x)) = g(x)`` idempotence): a full document, compared by exact string
equality after canonicalization.

Domain ``D`` — where the identity provably holds
------------------------------------------------
Documents built from:

* **paragraphs of prose, of any length** — the PDF hard-wraps long paragraphs at
  the page width; ``N`` reflows them, so wrapping does not break the identity;
* **bullet lists** (``-`` / ``*`` / ``+`` items, one line per item);
* **footnotes** — both numeric (``[^1]``) and named (``[^aa]``) labels. The
  renderer renumbers them and prints the texts at the page foot; ``N`` folds the
  footnote texts back to the end and drops the (non-recoverable) label, so the
  footnote *content* round-trips.

It holds across **multiple pages**: page-number footers md2star prints are removed
by ``N``. Determinism is real — rendering the same source twice yields byte-identical
extracted text — so the identity is stable, not flaky.

What ``N`` normalizes, and why each step is legitimate (not a fudge)
-------------------------------------------------------------------
1. Line endings ``\\r\\n`` / ``\\r`` → ``\\n`` (the extractor emits CRLF; cosmetic).
2. Blank lines dropped (vertical spacing is not content).
3. Standalone page-number lines (``^\\d+$``) dropped — **the "footer"** the round-trip
   must ignore; it is page furniture the PDF adds, absent from the source.
4. md2star's injected localized **date subtitle** dropped — the single element
   md2star adds on every render, by design (see :data:`_DATE_SUBTITLE`).
5. **Footnotes folded**: each ``[^label]: text`` definition's *text* is pulled to
   the end (in reference order), the inline ``[^label]`` reference is deleted, and
   the rendered superscript marker (a digit glued to the preceding word, e.g.
   ``citation.1``) is stripped. The label — numeric or named — is discarded on both
   sides because the renderer replaces it with a running number; only the footnote
   *text* is recoverable, and that is what round-trips.
6. Bullet markers (``-``, ``*``, ``+``, and LibreOffice's private-use bullet glyph
   ``U+F0B7``) normalized to ``"- "`` — maps both the source and the extracted PDF
   text to one spelling of "this is a list item".
7. **Prose reflow**: consecutive non-bullet lines are joined with single spaces.
   This undoes the PDF's hard line-wrapping. It also erases paragraph-break
   *positions* between adjacent prose paragraphs — a PDF's text flow does not
   preserve them, so ``N`` removes them on **both** sides rather than pretend they
   survive.

What is provably OUTSIDE ``D`` (cannot be recovered — a PDF has no such layer)
-----------------------------------------------------------------------------
* inline emphasis ``**bold**`` / ``*italic*`` / ``code`` → rendered as plain glyphs;
* heading **levels** (``#``, ``##``, …) → styled text; the level is not stored;
* **tables** → positioned cells and rules, not a grid model.

Their *text* survives a render; their *markup* does not, by construction — so
asserting their recovery would be dishonest, and ``D`` excludes them. The cheap,
structured direction (``md → docx → md`` with markup intact) is covered separately
by :mod:`tests.test_roundtrip` through Pandoc's native DOCX reader. Bullet items
are assumed to fit on one rendered line; a bullet long enough to wrap is out of
scope (its continuation line is indistinguishable from a new paragraph once the
list markers are gone).

Why kreuzberg is a test-only dependency
---------------------------------------
kreuzberg is heavy and only exercises the *verification* direction — it is never
part of md2star's ``md → docx/pptx/pdf`` runtime. It lives in the ``dev`` extra;
the module skips cleanly when kreuzberg, LibreOffice, or Pandoc is absent, and is
marked ``slow`` (a LibreOffice render plus extraction costs seconds). CI installs
the full toolchain in a dedicated job so this identity is *actually executed*, not
skipped.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path

import pytest

# Each leg has an external prerequisite; any one being absent makes the identity
# untestable rather than false, so the module skips as a unit on a bare machine:
#   - pandoc   : md2star's Markdown reader (first hop of f);
#   - soffice  : headless LibreOffice, how f renders DOCX → PDF;
#   - kreuzberg: the extractor g reads the PDF back with.
_HAS_PANDOC = shutil.which("pandoc") is not None
_HAS_SOFFICE = shutil.which("soffice") is not None or shutil.which("libreoffice") is not None
_HAS_KREUZBERG = importlib.util.find_spec("kreuzberg") is not None

pytestmark = [
    pytest.mark.skipif(
        not (_HAS_PANDOC and _HAS_SOFFICE and _HAS_KREUZBERG),
        reason="requires pandoc + libreoffice (soffice) + kreuzberg",
    ),
    pytest.mark.slow,
]

# A date-shaped subtitle line md2star stamps on every render, in the localized long
# form (English "Saturday, July 18, 2026" or French "18 juillet 2026"). It is the one
# element the pipeline adds that is absent from the source, so N removes it (step 4).
_DATE_SUBTITLE = re.compile(
    r"^(?:\w+,\s+\w+\s+\d{1,2},\s+\d{4}"   # English: Saturday, July 18, 2026
    r"|\d{1,2}\s+\w+\s+\d{4})$"            # French:  18 juillet 2026
)

# A line is a bullet if it starts with an ASCII list marker OR LibreOffice's
# private-use rendered bullet glyph U+F0B7 (what kreuzberg reads back from the PDF).
_BULLET = re.compile(
    # ASCII list markers plus the Unicode / private-use bullet glyphs a PDF
    # renderer (LibreOffice) may emit for a list item, written as explicit
    # \u escapes so the set is visible in source and portable across platforms:
    # - * +  U+2022 BULLET  U+00B7 MIDDLE DOT  U+F0B7 (Symbol-font bullet, PUA)
    # U+25CF BLACK CIRCLE  U+25E6 WHITE BULLET  U+2023 TRIANGULAR  U+2043 HYPHEN
    # U+2219 BULLET OPERATOR.
    r"^[-*+\u2022\u00b7\uf0b7\u25cf\u25e6\u2023\u2043\u2219]\s+"
)

# Markdown footnotes: a body reference ``[^label]`` and a definition
# ``[^label]: text``. The label may be numeric (``[^1]``) or named (``[^aa]``);
# md2star/LibreOffice renumber every footnote 1, 2, 3\u2026 by reference order, so the
# label never survives verbatim \u2014 and does not need to (the footnote *text* does).
_FN_DEF = re.compile(r"(?m)^\[\^[^\]]+\]:\s*(.*)$")   # a definition line; group 1 = its text
_FN_REF = re.compile(r"\[\^[^\]]+\]")                 # an inline reference in the body
# A rendered footnote superscript in the extracted text: a digit run glued directly
# to the preceding word/punctuation (``citation.1``) \u2014 distinct from a real number,
# which is preceded by a space (``page 42``), so this never eats genuine figures.
_SUPERSCRIPT = re.compile(r"(?<=[^\d\s])\d+\b")


def f(md_text: str, tmp_path: Path, tag: str) -> Path:
    """``f`` — render Markdown to a PDF through md2star's real CLI path.

    Parameters
    ----------
    md_text : str
        The Markdown source ``x`` to convert.
    tmp_path : pathlib.Path
        Pytest's per-test temporary directory; holds the ``.md`` input and
        the ``.pdf`` output.
    tag : str
        Short slug used to name the intermediate files uniquely within a test.

    Returns
    -------
    pathlib.Path
        Path to the freshly written PDF ``f(x)``.
    """
    # Call the exact entry point the CLI uses (not a subprocess) so the test
    # exercises the same code ``md2pdf`` runs; ``--offline`` keeps it off the network.
    from md2star.cli import _convert

    src = tmp_path / f"{tag}.md"
    out = tmp_path / f"{tag}.pdf"
    src.write_text(md_text, encoding="utf-8")
    rc = _convert("pdf", [str(src), "-o", str(out), "--offline"])

    # A non-zero return code means LibreOffice failed to render; name the tag so a
    # CI failure points straight at the offending fixture.
    assert rc == 0, f"md2pdf failed on {tag} (rc={rc})"
    return out


def g(pdf_path: Path) -> str:
    """``g`` — read a PDF back to text with kreuzberg (PLAIN preserves structure).

    Parameters
    ----------
    pdf_path : pathlib.Path
        The PDF produced by :func:`f`.

    Returns
    -------
    str
        The recovered plain text ``g(f(x))``. Each list item and each wrapped
        line is on its own physical line — the structure ``N`` needs to rebuild
        the source. (``OutputFormat.MARKDOWN`` is deliberately *not* used: it
        merges list items onto one line and drops the space at wrap points.)
    """
    # Imported lazily: the module-level skip guarantees kreuzberg is importable by
    # the time any test body runs.
    from kreuzberg import ExtractionConfig, OutputFormat, extract_file_sync

    cfg = ExtractionConfig(output_format=OutputFormat.PLAIN)
    return extract_file_sync(str(pdf_path), config=cfg).content


def _normal_form(text: str) -> str:
    """``N`` — the canonical normal form both sides of the identity are compared in.

    Implements the normalization steps documented in the module docstring:
    normalize line endings; **fold footnotes** (pull each definition's text to the
    end in reference order, and delete the inline reference plus its rendered
    superscript marker); drop blank / page-number / date-subtitle lines;
    canonicalize bullet markers to ``"- "``; and reflow wrapped prose. The same
    ``N`` is applied to the source ``x`` and to ``g(f(x))``; the identity is the
    exact string equality of the two results.

    Parameters
    ----------
    text : str
        Either the source Markdown ``x`` or the extracted text ``g(f(x))``.

    Returns
    -------
    str
        The canonical form: one ``"- item"`` line per bullet and one reflowed
        line per contiguous prose run, with footnote texts appended in order —
        matching where a render prints them.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Footnotes (step 5). Pull every definition's text out — in source order, which
    # is reference order for a well-formed document — so it can be appended at the
    # end, exactly where a single-page render prints the footnotes; then delete the
    # inline ``[^label]`` references from the body. The label itself is discarded on
    # both sides: the renderer replaces it with a running number, so only the text
    # is recoverable (and only the text needs to be).
    fn_texts: list[str] = []
    text = _FN_DEF.sub(lambda m: (fn_texts.append(m.group(1).strip()) or ""), text)
    text = _FN_REF.sub("", text)

    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        # Collapse a run of consecutive prose lines into a single reflowed
        # paragraph line (undoing PDF hard-wrapping), tagged so a prose line can
        # never accidentally equal a bullet line of the same text.
        if buf:
            out.append("P " + re.sub(r"\s+", " ", " ".join(buf)).strip())
            buf.clear()

    # Walk the body, then the footnote texts as trailing prose (so reflow merges
    # them into the closing paragraph exactly as the rendered page bottom does).
    # Guard order matters: strip the superscript marker, then test drop / bullet /
    # prose (a bare page-number and a bare footnote marker are both dropped here).
    for raw in text.split("\n") + fn_texts:
        # Remove a rendered footnote superscript glued to the preceding word
        # (``citation.1``) before any other classification.
        line = _SUPERSCRIPT.sub("", raw.strip())
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue                                   # blank lines
        if re.fullmatch(r"\d+", line):
            continue                                   # page-number footer OR footnote marker
        if _DATE_SUBTITLE.match(line):
            continue                                   # injected date subtitle
        if _BULLET.match(line):
            # a bullet ends the current prose run and emits a canonical item.
            flush()
            out.append("- " + _BULLET.sub("", line).strip())
            continue
        buf.append(line)                               # accumulate prose to reflow

    flush()
    return "\n".join(out)


def _identity_holds(md_text: str, tmp_path: Path, tag: str) -> None:
    """Assert the strict identity ``N(g(f(x))) == N(x)`` for one document.

    Parameters
    ----------
    md_text : str
        The source Markdown ``x`` (must lie in the domain ``D``).
    tmp_path : pathlib.Path
        Pytest temporary directory forwarded to :func:`f`.
    tag : str
        Unique slug for the intermediate files.
    """
    recovered = _normal_form(g(f(md_text, tmp_path, tag)))
    source = _normal_form(md_text)
    # Exact, whole-document string equality — the honest form of "g(f(x)) = x".
    assert recovered == source, (
        "round-trip is not the identity under N:\n"
        f"--- N(x) ---\n{source}\n--- N(g(f(x))) ---\n{recovered}"
    )


# ----------------------------- fixtures (all in D) -----------------------------

# Short, single-line paragraphs plus a bullet list: the simplest member of D.
_SHORT = (
    "The opening paragraph names Kreuzberg exactly once.\n\n"
    "- Alpha consolidation task\n"
    "- Beta migration task\n"
    "- Gamma cleanup task\n\n"
    "The closing paragraph mentions Payments and Latency.\n"
)

# A paragraph long enough to force the PDF renderer to wrap it across several
# physical lines — exercises the reflow branch (step 6) of N.
_LONG_PARA = (
    "This is a deliberately long paragraph that comfortably exceeds the printable "
    "page width so the PDF renderer must break it across several physical lines, "
    "which the normal form reflows back into one when it checks the identity."
)


def test_identity_short_prose_and_bullets(tmp_path: Path) -> None:
    """``g(f(x)) = x`` for short paragraphs interleaved with a bullet list."""
    _identity_holds(_SHORT, tmp_path, "short")


def test_identity_long_wrapping_paragraphs(tmp_path: Path) -> None:
    """``g(f(x)) = x`` when paragraphs wrap — reflow makes wrapping invisible."""
    x = "\n\n".join(_LONG_PARA for _ in range(4)) + "\n"
    _identity_holds(x, tmp_path, "long")


def test_identity_prose_and_bullets_with_wrapping(tmp_path: Path) -> None:
    """``g(f(x)) = x`` for wrapped prose *and* bullets in the same document."""
    x = _LONG_PARA + "\n\n- one item\n- two item\n- three item\n\n" + _LONG_PARA + "\n"
    _identity_holds(x, tmp_path, "mixed")


def test_identity_across_multiple_pages(tmp_path: Path) -> None:
    """``g(f(x)) = x`` across page breaks — page-number footers are normalized out."""
    # ~24 wrapping paragraphs guarantee several pages, so real page-number footers
    # appear in the extracted text and must be stripped by N (step 3).
    x = "\n\n".join(f"Paragraph {i}. {_LONG_PARA}" for i in range(1, 25))
    x += "\n\n- one\n- two\n"
    _identity_holds(x, tmp_path, "multipage")


def test_identity_with_numeric_footnotes(tmp_path: Path) -> None:
    """``g(f(x)) = x`` for prose + bullets + numeric-label footnotes ``[^1]``.

    The footnote references render as superscript numbers glued to the body text and
    the footnote texts print at the page foot; N folds them back so the content
    round-trips.
    """
    x = (
        "The claim needs a citation.[^1] And a second point follows.[^2]\n\n"
        "- Alpha item\n- Beta item\n\n"
        "A closing paragraph after the list.\n\n"
        "[^1]: Smith 2020, page 42.\n"
        "[^2]: An explanatory aside about the second point.\n"
    )
    _identity_holds(x, tmp_path, "fn_numeric")


def test_identity_with_named_footnotes(tmp_path: Path) -> None:
    """``g(f(x)) = x`` for named-label footnotes ``[^aa]`` / ``[^note]``.

    Named labels never survive a render (LibreOffice renumbers footnotes 1, 2, 3…),
    which is fine: only the footnote *text* is part of the identity, so ``[^aa]``
    round-trips exactly like ``[^1]``.
    """
    x = (
        "First fact requires support.[^aa] A separate remark needs one too.[^note]\n\n"
        "- one item\n- two item\n\n"
        "The final paragraph wraps things up.\n\n"
        "[^aa]: Reference the primary source here.\n"
        "[^note]: A short clarifying note for the reader.\n"
    )
    _identity_holds(x, tmp_path, "fn_named")


def test_render_is_deterministic(tmp_path: Path) -> None:
    """Rendering the same source twice yields identical extracted text.

    Determinism is what makes the identity a stable contract rather than a flaky
    coincidence: ``f`` and ``g`` are (byte-for-byte) functions of the input.
    """
    first = g(f(_SHORT, tmp_path, "det_a"))
    second = g(f(_SHORT, tmp_path, "det_b"))
    assert first == second
