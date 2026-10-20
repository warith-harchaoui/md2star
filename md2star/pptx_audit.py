"""Model-free audit of an assembled deck: what a reviewer would catch by eye.

:mod:`md2star.pptx_fit` decides, before assembly, whether a slide's content
*should* fit a candidate layout. This module asks the complementary question
*after* assembly, of the saved ``.pptx`` itself: given the shapes that actually
exist, with the geometry and the font sizes they actually carry, is anything
wrong with this deck? Five checks, all arithmetic on OOXML — no model, no
render, no network:

``off-slide``
    A shape extends past the canvas. Content that nobody will ever see.
``overlap``
    Two text shapes cover the same region. Text over a *picture* is a normal
    designer composition and is not flagged; text over text never is. A
    one-glyph ornament (:func:`md2star.pptx_assemble.is_ornament`) does not
    count as one of the two — a "01" inside a title's generous box is a
    designer's composition too, and cloned pages are full of them.
``ghost-placeholder``
    A placeholder the slide inherited from its layout and never filled. The
    assembler removes these (see
    :func:`md2star.pptx_assemble.drop_empty_placeholders`); this is the
    invariant re-checked on the file, which is the only place it matters.
``illegible-type``
    A run below :data:`LEGIBLE_MIN_PT`. Not the 30 pt ideal — the size below
    which a projected slide stops being readable at all.
``overrun``
    The text needs more room than its box gives it at the size it declares.
    Reported with the size that *would* fit, because PowerPoint's auto-shrink
    means the consequence is quiet (smaller type), not visible (clipped text).
    An observation about the deck's density, in the same spirit as
    :data:`md2star.pptx_fit.KAWASAKI_MIN_PT`: a finding, never an error.

Why bother, when :func:`md2star.pptx_assemble.eyeball_slides` already shows
each slide to a vision model? Because that loop needs a resolved VLM,
LibreOffice and poppler, while every failure above is *measurable*.
A geometry bug deserves arithmetic, not an opinion — and this way the quality
gate still runs on a laptop with no model at all, which is md2star's whole
offline-by-default posture. The dimensions are the ones PPTEval scores a deck
on by eye (Design: "proper layout ... element placement, and absence of
overlaps", arXiv 2501.03936); this is the half of that rubric a machine can
settle on its own.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation

from .logging import get_logger

# One-way dependency, on purpose: the assembler owns the placeholder vocabulary
# (it is what writes placeholders), the audit only reads it. Should the eyeball
# loop ever want to consume this module, it must import it inside the function
# — as md2star/cli.py does — rather than at module scope.
from .pptx_assemble import LATENT_KINDS, is_ornament, placeholder_kind
from .pptx_fit import AVG_CHAR_WIDTH_EM, EMU_PER_PT, FIT_SLACK, LINE_SPACING

logger = get_logger(__name__)

#: Point size below which a projected slide stops being readable from the back
#: of a room. Deliberately far below :data:`md2star.pptx_fit.KAWASAKI_MIN_PT`
#: (30 pt): that is the *ideal* this project reports against, while this is the
#: floor under which something has gone wrong — a caption nobody can read.
LEGIBLE_MIN_PT = 12.0

#: How far past the canvas edge a shape may sit before it counts as bleeding
#: off the slide, as a fraction of the canvas. Designer templates routinely
#: bleed a background band a hair past the edge on purpose, and rounding EMU
#: through inches leaves sub-point residue, so an exact test would cry wolf.
BLEED_TOLERANCE = 0.01

#: Shared area, as a fraction of the smaller shape's own area, above which two
#: text shapes are judged to collide. A few percent is a touching corner; a
#: tenth of a shape is a legibility problem.
OVERLAP_TOLERANCE = 0.10

#: Every finding kind this module can report, in descending severity. Used to
#: order a report and to keep the vocabulary closed (a typo'd kind in a caller
#: would otherwise sort and summarise silently).
KINDS: tuple[str, ...] = (
    "off-slide",
    "overlap",
    "ghost-placeholder",
    "illegible-type",
    "overrun",
)


@dataclass(frozen=True)
class Finding:
    """One thing wrong with one slide.

    Attributes
    ----------
    slide : int
        1-based slide number, as PowerPoint shows it.
    kind : str
        One of :data:`KINDS`.
    detail : str
        A sentence a human can act on, with the measurement in it.
    shape : str
        The offending shape's name, when a single shape owns the finding.
    """

    slide: int
    kind: str
    detail: str
    shape: str = ""

    def __str__(self) -> str:
        where = f" [{self.shape}]" if self.shape else ""
        return f"slide {self.slide}: {self.kind}{where} — {self.detail}"


# ── geometry helpers ─────────────────────────────────────────────────────────
def _box(shape) -> tuple[int, int, int, int] | None:
    """``(left, top, width, height)`` in EMU, or ``None`` when inherited.

    A shape that takes its position from its layout reports ``None`` for these,
    and python-pptx offers no resolution of the inheritance chain. Unknown
    geometry is skipped rather than guessed: a false "off-slide" on a shape
    whose real position is fine would train the reader to ignore the report.
    """
    left, top, width, height = shape.left, shape.top, shape.width, shape.height
    if None in (left, top, width, height) or width <= 0 or height <= 0:
        return None
    return (int(left), int(top), int(width), int(height))


def _intersection(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
    """Area shared by two EMU boxes (0 when they do not meet)."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = min(ax + aw, bx + bw) - max(ax, bx)
    dy = min(ay + ah, by + bh) - max(ay, by)
    return dx * dy if dx > 0 and dy > 0 else 0


def _runs_of(para) -> list[tuple[str, float | None]]:
    """One paragraph's ``(text, point size)`` runs.

    Paragraph-level size is the fallback for a run that declares none: that is
    the next link in OOXML's own inheritance chain, and it keeps a uniformly
    styled paragraph measurable. ``None`` survives only when the size comes
    from the master, where this module declines to guess.
    """
    para_pt = para.font.size.pt if para.font.size is not None else None
    return [
        (run.text, run.font.size.pt if run.font.size is not None else para_pt) for run in para.runs
    ]


def _runs(shape) -> list[tuple[str, float | None]]:
    """Every run in a shape, flattened."""
    return [run for para in shape.text_frame.paragraphs for run in _runs_of(para)]


def _needed_pt_height(shape, box: tuple[int, int, int, int]) -> tuple[float, float]:
    """Vertical points this shape's text needs, and the largest size in it.

    Uses :mod:`md2star.pptx_fit`'s character model — 0.5 em mean advance, 1.2
    line spacing — per paragraph, so a shape that mixes a 26 pt heading with
    16 pt bullets is measured as the sum of what each actually costs rather
    than at one averaged size.
    """
    width_pt = box[2] / EMU_PER_PT
    total = 0.0
    largest = 0.0
    for para in shape.text_frame.paragraphs:
        runs = _runs_of(para)
        text = "".join(t for t, _ in runs)
        sizes = [pt for _, pt in runs if pt]
        if not text.strip() or not sizes:
            continue  # blank, or fully inherited sizing: unknowable, so uncounted
        # The biggest run in a paragraph sets its line height, and (being the
        # widest) its characters-per-line — the conservative choice of the two.
        pt = max(sizes)
        largest = max(largest, pt)
        chars_per_line = max(1.0, width_pt // (pt * AVG_CHAR_WIDTH_EM))
        total += math.ceil(len(text) / chars_per_line) * pt * LINE_SPACING
    return total, largest


# ── the checks ───────────────────────────────────────────────────────────────
def _check_bounds(index: int, shape, box, canvas) -> list[Finding]:
    """Flag a shape that reaches past the canvas by more than the tolerance."""
    slide_w, slide_h = canvas
    left, top, width, height = box
    tol_x, tol_y = slide_w * BLEED_TOLERANCE, slide_h * BLEED_TOLERANCE
    # All four edges, in one finding: a shape pushed off the bottom-right
    # corner is one mistake, and reporting it twice would read as two.
    over = []
    if left < -tol_x:
        over.append(f"{(-left) / EMU_PER_PT:.0f}pt past the left edge")
    if top < -tol_y:
        over.append(f"{(-top) / EMU_PER_PT:.0f}pt past the top edge")
    if left + width > slide_w + tol_x:
        over.append(f"{(left + width - slide_w) / EMU_PER_PT:.0f}pt past the right edge")
    if top + height > slide_h + tol_y:
        over.append(f"{(top + height - slide_h) / EMU_PER_PT:.0f}pt past the bottom edge")
    if not over:
        return []
    return [Finding(index, "off-slide", ", ".join(over), shape.name)]


def _check_overlaps(
    index: int, texts: list[tuple[object, tuple[int, int, int, int]]]
) -> list[Finding]:
    """Flag pairs of text shapes that cover the same part of the slide."""
    findings: list[Finding] = []
    # Every unordered pair once: `texts[i + 1:]` rather than the full list, so
    # a collision is one finding and not a mutual pair of them.
    for i, (shape_a, box_a) in enumerate(texts):
        for shape_b, box_b in texts[i + 1 :]:
            shared = _intersection(box_a, box_b)
            if not shared:
                continue
            # Measured against the SMALLER shape: a caption swallowed by a
            # full-bleed text panel is a collision, even though the panel has
            # barely noticed it. The larger shape's area would hide that.
            smaller = min(box_a[2] * box_a[3], box_b[2] * box_b[3])
            fraction = shared / smaller if smaller else 0.0
            if fraction > OVERLAP_TOLERANCE:
                findings.append(
                    Finding(
                        index,
                        "overlap",
                        f"{shape_a.name!r} and {shape_b.name!r} share "
                        f"{fraction:.0%} of the smaller box",
                    )
                )
    return findings


def _check_type(index: int, shape) -> list[Finding]:
    """Flag runs below the legibility floor."""
    # A set, then sorted: one finding per shape listing each distinct offending
    # size, rather than one per run — a 40-line 8 pt table is a single problem.
    tiny = sorted({pt for text, pt in _runs(shape) if text.strip() and pt and pt < LEGIBLE_MIN_PT})
    if not tiny:
        return []
    sizes = ", ".join(f"{pt:g}pt" for pt in tiny)
    return [
        Finding(
            index,
            "illegible-type",
            f"{sizes} is under the {LEGIBLE_MIN_PT:g}pt legibility floor",
            shape.name,
        )
    ]


def _check_overrun(index: int, shape, box) -> list[Finding]:
    """Flag text that needs more vertical room than its box gives it."""
    needed, largest = _needed_pt_height(shape, box)
    available = box[3] / EMU_PER_PT
    if needed <= 0 or available <= 0 or needed <= available * FIT_SLACK:
        return []
    # Capacity scales with the square of the point size (line height *and*
    # characters per line both do), so the size that would fit is the current
    # one scaled by the square root of the shortfall — the same arithmetic as
    # pptx_fit.FitReport.implied_pt, applied to a real shape.
    implied = largest * math.sqrt(available / needed)
    return [
        Finding(
            index,
            "overrun",
            f"text needs {needed / available:.1f}x its box at {largest:g}pt "
            f"(fits at ~{implied:.0f}pt)",
            shape.name,
        )
    ]


# ── the audit ────────────────────────────────────────────────────────────────
def audit(deck: Path, *, canvas: tuple[int, int] | None = None) -> list[Finding]:
    """Audit a saved ``.pptx``, slide by slide.

    Parameters
    ----------
    deck : pathlib.Path
        The assembled presentation to inspect. Read-only; nothing is written.
    canvas : tuple of int, optional
        ``(width, height)`` in EMU to measure against. Defaults to the deck's
        own slide size, which is what you want unless you are checking a deck
        against a different target canvas.

    Returns
    -------
    list of Finding
        Sorted by slide, then by descending severity (:data:`KINDS` order).
        Empty means the deck passed every check.

    Examples
    --------
    >>> findings = audit(Path("deck.pptx"))  # doctest: +SKIP
    >>> print(summarise(findings))           # doctest: +SKIP
    layout audit: clean (12 slides)
    """
    prs = Presentation(str(deck))
    size = canvas or (prs.slide_width, prs.slide_height)
    findings: list[Finding] = []

    for index, slide in enumerate(prs.slides, start=1):
        # Collected across the slide, because an overlap is a property of a
        # PAIR: it cannot be judged while visiting either shape alone.
        texts: list[tuple[object, tuple[int, int, int, int]]] = []
        for shape in slide.shapes:
            box = _box(shape)
            # Bounds first, and for pictures too: an image half off the canvas
            # is the same defect as a text box half off it.
            if box is not None:
                findings += _check_bounds(index, shape, box, size)
            if not shape.has_text_frame or not shape.text_frame.text.strip():
                # An EMPTY placeholder is the ghost the assembler should have
                # removed; an empty plain shape is a designer's decoration, and
                # an empty date/footer/slide-number one is PowerPoint's to fill.
                if shape.is_placeholder and placeholder_kind(shape) not in LATENT_KINDS:
                    findings.append(
                        Finding(index, "ghost-placeholder", "unfilled placeholder", shape.name)
                    )
                continue
            findings += _check_type(index, shape)
            if box is not None:
                findings += _check_overrun(index, shape, box)
                if not is_ornament(shape.text_frame.text.strip()):
                    # A one-glyph ornament — the "01" of a numbered step, an
                    # arrow — sitting inside a title's generous box is the
                    # designer's own composition, not two blocks of text
                    # colliding. Same exemption, and same reason, as text
                    # over a picture.
                    texts.append((shape, box))
        findings += _check_overlaps(index, texts)

    # Slide order first (a reader fixes a deck front to back), severity within
    # a slide, then shape name so two runs over one deck report identically.
    order = {kind: i for i, kind in enumerate(KINDS)}
    findings.sort(key=lambda f: (f.slide, order.get(f.kind, len(KINDS)), f.shape))
    return findings


def summarise(findings: list[Finding], *, slides: int | None = None) -> str:
    """One line fit for stdout: what the audit found, or that it found nothing.

    Parameters
    ----------
    findings : list of Finding
        As returned by :func:`audit`.
    slides : int, optional
        Deck length, for the "clean" wording.

    Returns
    -------
    str
        A single line, never empty.

    Examples
    --------
    >>> summarise([], slides=12)
    'layout audit: clean (12 slides)'
    >>> summarise([Finding(3, "overlap", "x")])
    'layout audit: 1 finding on 1 slide (1 overlap)'
    """
    if not findings:
        where = f" ({slides} slides)" if slides else ""
        return f"layout audit: clean{where}"
    counts = {kind: sum(1 for f in findings if f.kind == kind) for kind in KINDS}
    breakdown = ", ".join(f"{n} {kind}" for kind, n in counts.items() if n)
    affected = len({f.slide for f in findings})
    plural = "s" if len(findings) > 1 else ""
    return (
        f"layout audit: {len(findings)} finding{plural} on {affected} "
        f"slide{'s' if affected > 1 else ''} ({breakdown})"
    )


def log_findings(findings: list[Finding]) -> None:
    """Send each finding to the logger at a level that matches its severity."""
    for finding in findings:
        # An overrun is a density observation (PowerPoint will auto-shrink the
        # text), so it is information; everything else is a real defect.
        level = logger.info if finding.kind == "overrun" else logger.warning
        level("%s", finding)


# ── `md2star audit` ──────────────────────────────────────────────────────────
#: The kinds that are defects rather than observations, and so decide the exit
#: status. An overrun is left out on purpose: PowerPoint auto-shrinks the text,
#: so a dense deck is a choice, not a breakage. `--strict` counts it too.
DEFECT_KINDS = frozenset(KINDS) - {"overrun"}


def main(argv: list[str] | None = None) -> int:
    """``md2star audit <deck.pptx>`` — measure a deck and report what is wrong.

    Works on **any** presentation, not only the ones md2star built: everything
    it checks is read off the OOXML, so a deck somebody made in PowerPoint is
    just as auditable. No model, no render, no network.

    Parameters
    ----------
    argv : list of str, optional
        Argument list; defaults to ``sys.argv[1:]`` as usual.

    Returns
    -------
    int
        ``0`` when nothing but observations were found, ``1`` when a defect
        was (see :data:`DEFECT_KINDS`, and ``--strict``), ``2`` on a usage or
        read error.
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="md2star audit",
        description="Report overlaps, off-canvas shapes, unreadable type and "
        "overfull boxes in a .pptx. Deterministic: no model, no network.",
    )
    parser.add_argument("deck", help="the .pptx to inspect (never modified)")
    parser.add_argument("--json", action="store_true", help="machine-readable findings")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="also fail on `overrun`, which is otherwise an observation",
    )
    args = parser.parse_args(argv)

    deck = Path(args.deck).expanduser()
    # Checked before opening: python-pptx reports a missing file as
    # "Package not found", which reads like a corrupt deck rather than a typo.
    if not deck.is_file():
        print(f"md2star audit: no such file: {deck}", file=sys.stderr)
        return 2
    try:
        findings = audit(deck)
    except Exception as exc:  # noqa: BLE001 — any reader error is the same answer
        # python-pptx raises several unrelated types for "that is not a pptx"
        # (PackageNotFoundError, KeyError, BadZipFile); the user needs one
        # sentence, not the taxonomy.
        print(f"md2star audit: cannot read {deck}: {exc}", file=sys.stderr)
        return 2

    slides = len(Presentation(str(deck)).slides)
    if args.json:
        print(json.dumps([vars(f) for f in findings], indent=2, ensure_ascii=False))
    else:
        for finding in findings:
            print(finding)
        print(summarise(findings, slides=slides))

    failing = DEFECT_KINDS | ({"overrun"} if args.strict else set())
    return 1 if any(f.kind in failing for f in findings) else 0
