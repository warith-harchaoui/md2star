"""Model-free audit of an assembled deck: what a reviewer would catch by eye.

:mod:`md2star.pptx_fit` decides, before assembly, whether a slide's content
*should* fit a candidate layout. This module asks the complementary question
*after* assembly, of the saved ``.pptx`` itself: given the shapes that actually
exist, with the geometry and the font sizes they actually carry, is anything
wrong with this deck? Six checks, all arithmetic on OOXML — no model, no
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
``low-contrast``
    Text a reader cannot separate from what is behind it, by the WCAG ratio
    (sRGB-linearised relative luminance), against the 3:1 floor large type
    earns and the 4.5:1 floor small type does not. The backdrop is resolved
    the way a renderer resolves it — shapes under the text, then the slide's
    background, then the layout's shapes and background, then the master's —
    because on a real template the colour panel a heading sits on is a shape
    on the *layout* while the layout's own background is the other half of the
    slide. Only runs that state their own colour are judged, and a backdrop
    this module cannot read (a photograph, a gradient) is left unjudged rather
    than guessed at.
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
from pptx.dml.color import MSO_COLOR_TYPE
from pptx.enum.dml import MSO_FILL
from pptx.enum.shapes import MSO_SHAPE_TYPE

from .i18n import gettext as _
from .i18n import ngettext as _n
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

#: WCAG 2.x calls type *large* at 18 pt, or 14 pt when bold, and asks 3:1 of
#: it against its background instead of the 4.5:1 it asks of body copy. A
#: slide is mostly large type by that definition, which is why the floor here
#: is usually the lenient one — and why a run that falls under it is a real
#: problem rather than a strict reading of a web rule.
CONTRAST_LARGE_PT = 18.0
CONTRAST_LARGE_BOLD_PT = 14.0
CONTRAST_MIN_LARGE = 3.0
CONTRAST_MIN_NORMAL = 4.5

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
    "low-contrast",
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
    measured_pt, fits_pt : float or None
        An ``overrun``'s declared size and the size that would fit. ``None``
        for every other kind, where the question does not arise.
    """

    slide: int
    kind: str
    detail: str
    shape: str = ""
    #: For an ``overrun``: the size the text declares, and the size that would
    #: fit. Carried as numbers, not only inside *detail*, because the eyeball
    #: loop consumes this (see
    #: :func:`md2star.pptx_assemble._measured_verdict`) and a loop that reads
    #: them can apply the exact correction instead of nudging toward it.
    measured_pt: float | None = None
    fits_pt: float | None = None

    def __str__(self) -> str:
        where = f" [{self.shape}]" if self.shape else ""
        # The kind keeps its English name inside a translated frame: it is the
        # closed vocabulary (:data:`KINDS`) a caller greps and a bug report
        # quotes, and a French build whose findings were named differently
        # would be a different machine interface, not a translated one.
        return _("slide %(n)d: %(kind)s%(where)s — %(detail)s") % {
            "n": self.slide,
            "kind": self.kind,
            "where": where,
            "detail": self.detail,
        }


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
        over.append(_("%(pt).0fpt past the left edge") % {"pt": (-left) / EMU_PER_PT})
    if top < -tol_y:
        over.append(_("%(pt).0fpt past the top edge") % {"pt": (-top) / EMU_PER_PT})
    if left + width > slide_w + tol_x:
        over.append(
            _("%(pt).0fpt past the right edge") % {"pt": (left + width - slide_w) / EMU_PER_PT}
        )
    if top + height > slide_h + tol_y:
        over.append(
            _("%(pt).0fpt past the bottom edge") % {"pt": (top + height - slide_h) / EMU_PER_PT}
        )
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
                        _("%(a)r and %(b)r share %(share).0f%% of the smaller box")
                        % {"a": shape_a.name, "b": shape_b.name, "share": fraction * 100},
                    )
                )
    return findings


# ── contrast: what a reader can actually read ────────────────────────────────
def _relative_luminance(rgb) -> float:
    """WCAG relative luminance of an ``RGBColor``, sRGB-linearised."""
    channels = []
    for raw in (rgb[0], rgb[1], rgb[2]):
        c = raw / 255.0
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(a, b) -> float:
    """Contrast ratio between two colours, 1:1 (identical) to 21:1 (b/w)."""
    first, second = _relative_luminance(a), _relative_luminance(b)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _solid_rgb(shape):
    """The shape's own solid fill as an ``RGBColor``, or ``None``.

    ``None`` covers everything this check cannot responsibly resolve: a
    gradient, a pattern, a theme reference, a picture fill, and a shape with no
    fill of its own. The caller treats that as "keep looking", never as "this
    is white".
    """
    try:
        fill = shape.fill
        if fill.type != MSO_FILL.SOLID:
            return None
        return fill.fore_color.rgb
    except Exception:  # noqa: BLE001 — a picture/graphic frame has no fill at all
        return None


def _covers(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
    """Whether *outer* contains *inner* whole.

    Containment, not overlap, and deliberately: a text box lying across two
    backgrounds — half on a designer's colour panel, half on the dark slide —
    has no single contrast ratio, and inventing one would be worse than saying
    nothing. Those are left unjudged.
    """
    return (
        outer[0] <= inner[0]
        and outer[1] <= inner[1]
        and outer[0] + outer[2] >= inner[0] + inner[2]
        and outer[1] + outer[3] >= inner[1] + inner[3]
    )


def _backdrop_in(shapes, box, *, below=None):
    """Topmost resolvable colour behind *box* among *shapes*.

    Walks back-to-front like a renderer does, so the nearest thing under the
    text wins. Returns ``(rgb, True)`` when a colour was found, ``(None,
    False)`` when nothing here is behind it, and ``(None, True)`` when
    something is — a picture, a gradient — that this check cannot read: that
    is a "stop looking", because whatever is further back is not what the
    reader sees.
    """
    ordered = list(shapes)
    if below is not None:
        ordered = ordered[: ordered.index(below)]
    for candidate in reversed(ordered):
        candidate_box = _box(candidate)
        if candidate_box is None or not _covers(candidate_box, box):
            continue
        rgb = _solid_rgb(candidate)
        if rgb is not None:
            return rgb, True
        if candidate.shape_type == MSO_SHAPE_TYPE.PICTURE:
            return None, True  # a photograph: unknowable, and not worth guessing
    return None, False


def _background_of(part):
    """A slide/layout/master's own background colour, or ``None``."""
    try:
        fill = part.background.fill
        return fill.fore_color.rgb if fill.type == MSO_FILL.SOLID else None
    except Exception:  # noqa: BLE001 — no explicit background is the common case
        return None


def _backdrop(slide, shape, box):
    """What a reader sees behind *shape*, resolved the way a renderer would.

    Shapes under it on the slide, then the slide's own background, then the
    layout's shapes and background, then the master's. The chain matters: on a
    real designer template the colour panel a title sits on is a shape **on the
    layout**, while the layout's own background is the dark half of the slide —
    read only the latter and a black heading on a lime panel looks like black
    on black.
    """
    rgb, blocked = _backdrop_in(slide.shapes, box, below=shape)
    if rgb is not None or blocked:
        return rgb
    own = _background_of(slide)
    if own is not None:
        return own
    layout = slide.slide_layout
    rgb, blocked = _backdrop_in(layout.shapes, box)
    if rgb is not None or blocked:
        return rgb
    inherited = _background_of(layout)
    if inherited is not None:
        return inherited
    master = layout.slide_master
    rgb, blocked = _backdrop_in(master.shapes, box)
    if rgb is not None or blocked:
        return rgb
    return _background_of(master)


def _check_contrast(index: int, slide, shape, box) -> list[Finding]:
    """Flag text a reader cannot separate from what is behind it.

    Only runs that state their own colour are judged. A run that inherits one
    from the theme is left alone for the same reason an inherited size is: the
    value comes from the designer's master, and guessing at it would invent
    findings rather than report them. That is the known limit of this check,
    and it is a limit in the conservative direction.
    """
    behind = _backdrop(slide, shape, box)
    if behind is None:
        return []
    worst: tuple[float, float, object] | None = None
    for paragraph in shape.text_frame.paragraphs:
        for run in paragraph.runs:
            if not run.text.strip():
                continue
            colour = run.font.color
            try:
                rgb = colour.rgb if colour.type == MSO_COLOR_TYPE.RGB else None
            except Exception:  # noqa: BLE001 — an unresolvable colour is not a finding
                rgb = None
            if rgb is None:
                continue
            size = run.font.size.pt if run.font.size else LEGIBLE_MIN_PT
            large = size >= CONTRAST_LARGE_PT or (run.font.bold and size >= CONTRAST_LARGE_BOLD_PT)
            floor = CONTRAST_MIN_LARGE if large else CONTRAST_MIN_NORMAL
            ratio = _contrast_ratio(rgb, behind)
            if ratio < floor and (worst is None or ratio < worst[0]):
                worst = (ratio, floor, rgb)
    if worst is None:
        return []
    ratio, floor, rgb = worst
    return [
        Finding(
            index,
            "low-contrast",
            _("#%(fg)s on #%(bg)s is %(ratio).1f:1, under the %(floor)g:1 floor")
            % {"fg": rgb, "bg": behind, "ratio": ratio, "floor": floor},
            shape.name,
        )
    ]


def _check_type(index: int, shape) -> list[Finding]:
    """Flag runs below the legibility floor."""
    # A set, then sorted: one finding per shape listing each distinct offending
    # size, rather than one per run — a 40-line 8 pt table is a single problem.
    tiny = sorted({pt for text, pt in _runs(shape) if text.strip() and pt and pt < LEGIBLE_MIN_PT})
    if not tiny:
        return []
    sizes = ", ".join(f"{pt:g}pt" for pt in tiny)
    # One message with the sizes pre-joined: a language that needs a different
    # separator can still change the sentence around them, and the list itself
    # is numbers, which read the same everywhere.
    return [
        Finding(
            index,
            "illegible-type",
            _("%(sizes)s is under the %(floor)gpt legibility floor")
            % {"sizes": sizes, "floor": LEGIBLE_MIN_PT},
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
            _("text needs %(times).1fx its box at %(pt)gpt (fits at ~%(fits).0fpt)")
            % {"times": needed / available, "pt": largest, "fits": implied},
            shape.name,
            measured_pt=largest,
            fits_pt=implied,
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
                        Finding(
                            index,
                            "ghost-placeholder",
                            _("unfilled placeholder"),
                            shape.name,
                        )
                    )
                continue
            findings += _check_type(index, shape)
            if box is not None:
                findings += _check_overrun(index, shape, box)
                findings += _check_contrast(index, slide, shape, box)
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
        if slides:
            return _("layout audit: clean (%(slides)d slides)") % {"slides": slides}
        return _("layout audit: clean")
    counts = {kind: sum(1 for f in findings if f.kind == kind) for kind in KINDS}
    # The kind names are the closed machine vocabulary (:data:`KINDS`) and stay
    # in English in every language: they are what a caller greps and what an
    # issue report quotes. Only the sentence around them is translated.
    breakdown = ", ".join(f"{n} {kind}" for kind, n in counts.items() if n)
    affected = len({f.slide for f in findings})
    # Two separate plural lookups rather than one sentence with two numbers:
    # "3 findings on 1 slide" is a real outcome, so each count has to choose
    # its own form — and gettext's plural rules work on one number at a time.
    things = _n("%(n)d finding", "%(n)d findings", len(findings)) % {"n": len(findings)}
    where = _n("%(n)d slide", "%(n)d slides", affected) % {"n": affected}
    return _("layout audit: %(things)s on %(where)s (%(breakdown)s)") % {
        "things": things,
        "where": where,
        "breakdown": breakdown,
    }


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


def run(deck_path: str, *, as_json: bool = False, strict: bool = False) -> int:
    """``md2star audit <deck.pptx>`` — measure a deck and report what is wrong.

    Works on **any** presentation, not only the ones md2star built: everything
    it checks is read off the OOXML, so a deck somebody made in PowerPoint is
    just as auditable. No model, no render, no network.

    The flags arrive parsed: since 3.10.0 this package has exactly one command
    line, built with click in :mod:`md2star.cli`, so nothing here re-parses an
    argv.

    Parameters
    ----------
    deck_path : str
        The ``.pptx`` to inspect. Never modified.
    as_json : bool, optional
        Emit the findings as JSON instead of one line each plus a summary.
    strict : bool, optional
        Also fail on ``overrun``, which is otherwise an observation.

    Returns
    -------
    int
        ``0`` when nothing but observations were found, ``1`` when a defect
        was (see :data:`DEFECT_KINDS`, and *strict*), ``2`` on a usage or
        read error.
    """
    import json

    deck = Path(deck_path).expanduser()
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
    if as_json:
        # Null-free: `measured_pt` / `fits_pt` only exist on an overrun, and a
        # consumer should see a key when it means something rather than a
        # column of nulls on every other kind.
        payload = [{k: v for k, v in vars(f).items() if v is not None} for f in findings]
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for finding in findings:
            print(finding)
        print(summarise(findings, slides=slides))

    failing = DEFECT_KINDS | ({"overrun"} if strict else set())
    return 1 if any(f.kind in failing for f in findings) else 0
