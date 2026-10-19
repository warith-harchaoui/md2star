"""Does this content actually *fit* this layout? — arithmetic, not taste.

The layout selector in :mod:`md2star.pptx_layout` asks an LLM to match a slide
to one of the designer's layouts, and a VLM to confirm the pick visually. Both
stages were given only the slide's **title** and a list of **categorical**
cues ("has a table", "has bullets"). Neither was told *how much* content there
is, and neither was told how large the chosen layout's placeholders are — even
though the catalog already extracts every placeholder's box in EMU.

So the system could cheerfully put nine long bullets into a layout the designer
drew for three short ones. Nothing failed; PowerPoint just shrank the text, or
let it spill past the placeholder. The deck came out looking unlike the template
it was supposedly built from.

This module closes that gap by making the question measurable.

The missing constant: a minimum font size
-----------------------------------------
"Does this text fit?" has no answer until you fix how small the text is allowed
to get — shrink far enough and anything fits, which is exactly the failure above.

We take the floor from **Guy Kawasaki's 10/20/30 rule**: ten slides, twenty
minutes, **thirty point** type. The thirty is the operative part here. Once a
font floor exists, a placeholder of known EMU dimensions has a *computable*
capacity, and "will this fit?" becomes arithmetic rather than judgement.

The thirty is a **target, not a gate**. Plenty of legitimate decks cannot hold
to it — a technical appendix, a training deck, a slide that genuinely carries a
dense table. So overflow past the floor is scored as a graded penalty and
reported in words, never used to disqualify a layout outright. The only hard
refusals are structural and have nothing to do with type size: an image with
nowhere to put it, or body text with no body placeholder at all. Those are not
"too much content", they are "the wrong shape of slide".

A caller who does want the rule enforced passes ``strict=True`` and gets
disqualification instead of a penalty.

How capacity is estimated
-------------------------
From the placeholder box, the font floor, and two typographic constants:

* ``AVG_CHAR_WIDTH_EM = 0.5`` — mean advance width of a character in a
  sans-serif face, as a fraction of the em. The widely used figure for
  Arial/Helvetica/Inter-class faces; CSS's ``ch`` unit (the width of "0") runs
  wider, which is why it is not used here.
* ``LINE_SPACING = 1.2`` — single line spacing as OOXML renders it.

Both are approximations, deliberately. The alternative is real font metrics,
which means shipping or locating the template's actual font files;
``python-pptx``'s own ``fit_text`` takes that route and requires the caller to
hand it a font path. For *choosing between layouts* a consistent estimate is
worth more than an exact one: every candidate is measured the same way, so the
ranking holds even where the absolute numbers drift. ``FIT_SLACK`` keeps the
decision off the knife edge.

How candidates are scored
-------------------------
Two ideas from the literature, plus one from the brief:

* **Occupancy matching.** SlideGen (arXiv 2512.04529) scores layout aesthetics
  with a geometry-aware density term ``1 - |ρ - τ|``, where ρ is the fraction of
  available space the content occupies and τ ≈ 0.55 the target — calibrated
  against 40 human raters (ρ = 0.82 correlation with their preferences). A
  slide at 15 % occupancy looks abandoned; at 95 % it looks crammed. We reuse
  the term directly.
* **Element-count and aspect matching.** SlideGen's Arranger picks "based on
  the number and types of elements, and on the size and aspect ratio of the
  visuals". We match image count against ``pic`` placeholder count, and a
  slide's image against whether the layout has anywhere to put one.
* **Image-forward, text-sparse.** A slide that is one image and few words is
  the target, not a fallback. Sparse text on an image-bearing layout is
  rewarded; an image with nowhere to go is penalised hard.

Nothing here applies styling. The design stays the designer's; this only decides
*which* of their slides a given piece of content belongs on, and says so with
numbers that can be argued with.

Author
------
Warith HARCHAOUI, https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

# ── constants, each with its reason ──────────────────────────────────────────

#: EMU per point. OOXML's fixed conversion (914400 EMU per inch, 72 pt/inch).
EMU_PER_PT = 12700

#: The font-size target, in points. Guy Kawasaki's 10/20/30. Everything here is
#: measured relative to this number, but it is an ideal rather than a
#: requirement: a slide that overruns it is penalised and reported, not
#: rejected. Raise it for a stricter deck; lower it when the content genuinely
#: warrants more text on the slide.
KAWASAKI_MIN_PT = 30.0

#: Slides per deck, same rule, same standing: exceeded is an observation, never
#: an error. Some decks legitimately are not pitches.
KAWASAKI_MAX_SLIDES = 10

#: Mean character advance as a fraction of the em, for a sans-serif face.
AVG_CHAR_WIDTH_EM = 0.5

#: Single line spacing, as rendered.
LINE_SPACING = 1.2

#: Target occupancy — SlideGen's τ. Neither abandoned nor crammed.
TARGET_OCCUPANCY = 0.55

#: How much text a title-only layout can absorb as a caption before it stops
#: being a plausible host. Roughly one spoken line: the "few words" half of
#: "one image and few words".
CAPTION_CHARS = 140

#: Tolerance on the fit verdict. The capacity estimate is approximate, so a
#: slide that overruns by a few percent is not called impossible; one that
#: overruns by a third is.
FIT_SLACK = 1.15

#: Placeholder kinds that hold prose. ``body`` and ``subTitle`` in OOXML;
#: ``obj`` is the generic content placeholder pandoc targets.
_BODY_KINDS = frozenset({"body", "subTitle", "obj", "tbl", "chart"})

#: Placeholder kinds that hold a title line.
_TITLE_KINDS = frozenset({"title", "ctrTitle"})

#: Placeholder kinds that hold a picture.
_PIC_KINDS = frozenset({"pic", "media", "clipArt"})


# ── measuring the content ────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*(?:[-*]|\d+\.)\s+(.*)$", re.MULTILINE)
_HEADING_RE = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)
_ATTR_RE = re.compile(r"\{\.[^}]*\}")
_INLINE_MARKUP_RE = re.compile(r"[*_`>]+")


@dataclass
class ContentMetrics:
    """How much of what a slide actually holds.

    Counts visible text, not markup: the question is what a reader sees, so
    fence bodies, image syntax and bullet markers do not inflate the totals.
    """

    title_chars: int = 0
    body_chars: int = 0
    bullet_count: int = 0
    longest_bullet_chars: int = 0
    image_count: int = 0
    table_rows: int = 0
    table_cols: int = 0
    code_lines: int = 0
    #: The author marked this slide as a single large statement ({.big}).
    #: Structural, not stylistic: it wants a title-only layout, with no body
    #: box sitting empty underneath it.
    big_statement: bool = False

    @property
    def word_count(self) -> int:
        """Rough word count of the body, for the sparsity reward."""
        # 5.5 characters per word including its trailing space is the standard
        # English-prose figure; exact enough for a "few words?" judgement.
        return int(round(self.body_chars / 5.5))

    @property
    def is_sparse(self) -> bool:
        """True for the one-image-and-few-words slide this suite aims at.

        A table or a code block disqualifies it however few words surround
        them: thirteen rows of figures is not a sparse slide, and counting only
        prose would have called it one.
        """
        return (
            self.word_count <= 25
            and self.bullet_count <= 4
            and self.table_rows == 0
            and self.code_lines == 0
        )


def measure(title: str, body: str) -> ContentMetrics:
    """Measure *body* (and *title*) into a :class:`ContentMetrics`.

    Parameters
    ----------
    title : str
        The slide's heading text, already stripped of attribute syntax.
    body : str
        The slide's full Markdown source, heading included.

    Returns
    -------
    ContentMetrics
        Counts of everything the fit computation needs.

    Examples
    --------
    >>> m = measure("Results", "# Results\\n\\n- one\\n- two\\n")
    >>> m.bullet_count
    2
    >>> m.image_count
    0
    """
    m = ContentMetrics(title_chars=len(title or ""))
    m.big_statement = bool(re.search(r"\{\.big\}", body))

    # Code fences: count their lines, then remove them so their contents do
    # not count as prose (a fence is laid out verbatim, not wrapped).
    fences = _FENCE_RE.findall(body)
    m.code_lines = sum(block.count("\n") - 1 for block in fences)
    rest = _FENCE_RE.sub("", body)

    # Images are placed, not read: count them and drop the syntax.
    m.image_count = len(_IMAGE_RE.findall(rest))
    rest = _IMAGE_RE.sub("", rest)

    # Table geometry drives which layouts can host it at all.
    rows = _TABLE_ROW_RE.findall(rest)
    # A Markdown table's separator row (|---|---|) is structure, not content.
    data_rows = [r for r in rows if not re.fullmatch(r"[\s|:-]+", r)]
    m.table_rows = len(data_rows)
    if data_rows:
        m.table_cols = max(r.count("|") - 1 for r in data_rows)
    rest = _TABLE_ROW_RE.sub("", rest)

    bullets = [b.strip() for b in _BULLET_RE.findall(rest)]
    m.bullet_count = len(bullets)
    m.longest_bullet_chars = max((len(b) for b in bullets), default=0)

    # Visible prose: headings, attribute spans and inline markup removed.
    prose = _HEADING_RE.sub("", rest)
    prose = _ATTR_RE.sub("", prose)
    prose = _INLINE_MARKUP_RE.sub("", prose)
    prose = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", prose, flags=re.MULTILINE)
    m.body_chars = len(" ".join(prose.split()))
    return m


# ── measuring the container ──────────────────────────────────────────────────


@dataclass
class Capacity:
    """What one placeholder box can hold at a given font floor."""

    lines: int = 0
    chars_per_line: int = 0

    @property
    def chars(self) -> int:
        """Total characters the box holds at the floor font size."""
        return self.lines * self.chars_per_line


def placeholder_capacity(
    emu: tuple[int, int, int, int] | None, *, min_pt: float = KAWASAKI_MIN_PT
) -> Capacity:
    """Estimate how much text a placeholder holds at *min_pt*.

    Parameters
    ----------
    emu : tuple of int, or None
        ``(left, top, width, height)`` in EMU, as the catalog extracts it.
        ``None`` (a layout that declares a placeholder without geometry)
        yields an empty capacity, which the caller reads as "unknown".
    min_pt : float, default :data:`KAWASAKI_MIN_PT`
        The font floor. Capacity scales roughly as its inverse square: half
        the point size holds about four times the text.

    Returns
    -------
    Capacity
        Lines, characters per line, and their product.

    Examples
    --------
    A half-slide body box on a 16:9 deck, at 30 pt:

    >>> cap = placeholder_capacity((0, 0, 4572000, 2571750))
    >>> cap.lines > 0 and cap.chars_per_line > 0
    True
    """
    if not emu:
        return Capacity()
    _, _, width, height = emu
    if width <= 0 or height <= 0 or min_pt <= 0:
        return Capacity()

    width_pt = width / EMU_PER_PT
    height_pt = height / EMU_PER_PT
    line_height_pt = min_pt * LINE_SPACING
    char_width_pt = min_pt * AVG_CHAR_WIDTH_EM

    lines = int(height_pt // line_height_pt)
    chars_per_line = int(width_pt // char_width_pt)
    return Capacity(lines=max(0, lines), chars_per_line=max(0, chars_per_line))


def _kinds(layout: object) -> list[str]:
    """The placeholder kinds a layout declares, defensively."""
    phs = getattr(layout, "placeholders", None) or []
    return [getattr(p, "kind", "") or "" for p in phs]


def _capacity_for(layout: object, kinds: frozenset[str], min_pt: float) -> Capacity:
    """Summed capacity of every placeholder on *layout* matching *kinds*.

    Summed rather than maxed because a two-column layout genuinely holds the
    text of both of its boxes.
    """
    total = Capacity()
    for p in getattr(layout, "placeholders", None) or []:
        if (getattr(p, "kind", "") or "") in kinds:
            cap = placeholder_capacity(getattr(p, "emu", None), min_pt=min_pt)
            # Keep the widest line and sum the lines: the usable shape of two
            # stacked boxes is closer to that than to either box alone.
            total.lines += cap.lines
            total.chars_per_line = max(total.chars_per_line, cap.chars_per_line)
    return total


# ── the verdict ──────────────────────────────────────────────────────────────


@dataclass
class FitReport:
    """Whether a slide's content can go on a layout, and how well it sits there.

    The two verdicts are deliberately separate, because they answer different
    questions:

    ``fits``
        Can this content be placed here at all? ``False`` only for structural
        impossibilities — an image with no picture placeholder, body text with
        no body placeholder. Never merely because there is a lot of text.
    ``overruns``
        Does the text exceed what the layout holds at the font target? An
        observation, scored as a penalty and explained in ``reasons``. A deck
        that overruns everywhere is still a deck; it is just not a 30 pt one.
    """

    fits: bool = True
    overruns: bool = False
    occupancy: float = 0.0
    score: float = 0.0
    capacity_chars: int = 0
    needed_chars: int = 0
    #: Contribution of the compositional principles (balance, reading order,
    #: alignment, thirds). Kept separate from ``score`` so a caller can see
    #: whether a layout won on capacity or on composition.
    composition: float = 0.0
    reasons: list[str] = field(default_factory=list)

    @property
    def overflow_chars(self) -> int:
        """Characters beyond what the layout holds at the font target."""
        return max(0, self.needed_chars - self.capacity_chars)

    @property
    def implied_pt(self) -> float:
        """The font size this content would actually need to fit here.

        Capacity scales with the inverse square of the point size, so the size
        that *would* fit is the target scaled by ``sqrt(capacity / needed)``.
        Reported rather than applied: it tells an author "this slide is a 22 pt
        slide" instead of silently making it one.
        """
        if self.needed_chars <= 0 or self.capacity_chars <= 0:
            return KAWASAKI_MIN_PT
        ratio = self.capacity_chars / self.needed_chars
        return min(KAWASAKI_MIN_PT, KAWASAKI_MIN_PT * math.sqrt(ratio))


def _occupancy_score(occupancy: float) -> float:
    """SlideGen's occupancy-match term, clipped to ``[0, 1]``.

    Peaks at :data:`TARGET_OCCUPANCY` and falls away on both sides: a nearly
    empty box and a nearly full one are both worse than a comfortable one.
    """
    return max(0.0, 1.0 - abs(occupancy - TARGET_OCCUPANCY))


def evaluate(
    metrics: ContentMetrics,
    layout: object,
    *,
    min_pt: float = KAWASAKI_MIN_PT,
    strict: bool = False,
    canvas: tuple[int, int] | None = None,
) -> FitReport:
    """Score how well *layout* can host the content described by *metrics*.

    Parameters
    ----------
    metrics : ContentMetrics
        The measured slide, from :func:`measure`.
    layout : object
        A :class:`md2star.pptx_layout.LayoutInfo`-shaped object: anything with
        ``placeholders`` (each having ``kind`` and ``emu``) and ``name``.
    min_pt : float, default :data:`KAWASAKI_MIN_PT`
        The font floor the verdict is relative to.

    Returns
    -------
    FitReport
        ``fits`` is the hard verdict; ``score`` ranks the layouts that do fit.
        ``reasons`` explains both, in words meant for a human or a prompt.

    Notes
    -----
    ``fits=False`` is a statement about geometry, not taste: the content cannot
    be shown on that layout without going below the font floor. The caller is
    expected to exclude such layouts from the candidate set rather than rank
    them last.
    """
    report = FitReport()
    kinds = _kinds(layout)
    body_cap = _capacity_for(layout, _BODY_KINDS, min_pt)
    pic_count = sum(1 for k in kinds if k in _PIC_KINDS)
    has_title = any(k in _TITLE_KINDS for k in kinds)

    # Text the body boxes must hold. A table's cells and a fence's lines are
    # laid out rather than wrapped, so they are charged by their own geometry:
    # a row costs a line, a fence line costs a line.
    needed = metrics.body_chars
    structural_lines = metrics.table_rows + metrics.code_lines
    if structural_lines and body_cap.chars_per_line:
        needed += structural_lines * body_cap.chars_per_line
    report.needed_chars = needed
    report.capacity_chars = body_cap.chars

    # --- structural constraints (the only hard refusals) --------------------
    # These are about the *shape* of the slide, not the amount of text. A
    # layout with nowhere to put a picture cannot host a slide that has one, at
    # any font size, so there is nothing to trade off.
    if metrics.image_count and not pic_count:
        report.fits = False
        report.reasons.append(
            f"{metrics.image_count} image(s) but the layout has no picture placeholder"
        )
    # A table or a code block needs somewhere laid-out to live, and that is a
    # body/table placeholder. Charge it separately from the text: a title-only
    # layout has chars_per_line == 0, so the structural charge above multiplies
    # out to nothing and a thirteen-row table would otherwise look weightless.
    if structural_lines and body_cap.chars == 0:
        report.fits = False
        what = "table" if metrics.table_rows else "code block"
        report.reasons.append(f"{structural_lines}-line {what} but no body or table placeholder")
    if needed > 0 and body_cap.chars == 0:
        # A layout with no body box is not thereby useless. "One image and a
        # line under it" is the deck this suite is aiming for, and the line
        # can ride in the title or as a caption. Rejecting the template's best
        # photo layout over four words would be exactly backwards -- so a
        # caption's worth of text is tolerated, and anything more is not.
        if needed <= CAPTION_CHARS:
            report.reasons.append(f"no body box; {needed} chars will ride in the title or caption")
        else:
            report.fits = False
            report.reasons.append(f"body text ({needed} chars) but no sized body placeholder")

    # --- overrun: an observation, not a refusal -----------------------------
    # 10/20/30 is an ideal. A dense table or a technical appendix legitimately
    # breaks it, and a selector that disqualified every roomy-enough layout
    # would leave such a deck with nothing to choose from. So this is graded.
    if body_cap.chars > 0 and needed > body_cap.chars * FIT_SLACK:
        report.overruns = True
        report.reasons.append(
            f"needs ~{needed} chars, holds ~{body_cap.chars} at {min_pt:g}pt "
            f"(~{report.implied_pt:.0f}pt would fit)"
        )
        if strict:
            report.fits = False
    if metrics.title_chars and not has_title:
        # Not fatal: a title can be rendered into the body box. Worth saying.
        report.reasons.append("no title placeholder; the heading will share the body box")

    # --- soft scoring -------------------------------------------------------
    if body_cap.chars > 0:
        report.occupancy = needed / body_cap.chars
    elif needed == 0:
        # An image-only slide on an image layout is a perfect fit, not an
        # empty one: score it at the target rather than at zero.
        report.occupancy = TARGET_OCCUPANCY if metrics.image_count else 0.0

    score = _occupancy_score(report.occupancy)

    # Element-count match on pictures, SlideGen's Arranger criterion.
    if metrics.image_count and pic_count:
        if metrics.image_count == pic_count:
            score += 0.30
            report.reasons.append(f"picture placeholders match image count ({pic_count})")
        else:
            score += 0.15
            report.reasons.append(
                f"{pic_count} picture placeholder(s) for {metrics.image_count} image(s)"
            )
    elif pic_count and not metrics.image_count:
        # A picture box with nothing to put in it reads as a hole in the slide.
        score -= 0.20 * pic_count
        report.reasons.append(f"{pic_count} picture placeholder(s) would be left empty")

    # A big statement wants the stage to itself: a title box and nothing else.
    # An empty body box under a four-word headline is the thing the author was
    # trying to avoid by marking it {.big}.
    if metrics.big_statement:
        if has_title and body_cap.chars == 0 and not pic_count:
            score += 0.40
            report.reasons.append("title-only layout for a big statement")
        elif body_cap.chars > 0:
            score -= 0.25
            report.reasons.append("a big statement would leave this body box empty")

    # Image-forward and text-sparse: the deck this suite is aiming for.
    if metrics.is_sparse and pic_count and metrics.image_count:
        score += 0.25
        report.reasons.append("one image, few words")

    # One bullet per line is the readable case; many short bullets crammed
    # into few lines is not.
    if metrics.bullet_count and body_cap.lines:
        if metrics.bullet_count > body_cap.lines:
            score -= 0.20
            report.reasons.append(
                f"{metrics.bullet_count} bullets into ~{body_cap.lines} lines at {min_pt:g}pt"
            )

    # Overrunning the target costs, proportionally to how far past it we are,
    # so a layout that holds 90 % of the text still outranks one holding 40 %.
    if report.overruns and report.capacity_chars:
        excess = report.needed_chars / report.capacity_chars  # > 1
        score -= min(0.60, 0.30 * (excess - 1.0))

    # Composition ranks layouts that can already host the content; it never
    # rescues one that cannot, which is why it is added rather than blended.
    comp, comp_reasons = composition(metrics, layout, canvas)
    score += comp
    report.composition = comp
    report.reasons.extend(comp_reasons)

    report.score = 0.0 if not report.fits else max(0.0, score)
    return report


def rank(
    metrics: ContentMetrics,
    layouts: list,
    *,
    min_pt: float = KAWASAKI_MIN_PT,
    strict: bool = False,
    canvas: tuple[int, int] | None = None,
) -> list[tuple[object, FitReport]]:
    """Order *layouts* best-first for this content.

    Structurally impossible layouts sort last but are still returned with their
    report, so a caller can show *why* something was passed over instead of
    only what won. The list is never empty when *layouts* is not: there is
    always a best available choice, even for a deck that overruns everywhere.
    """
    scored = [
        (lay, evaluate(metrics, lay, min_pt=min_pt, strict=strict, canvas=canvas))
        for lay in layouts
    ]
    scored.sort(key=lambda pair: (pair[1].fits, pair[1].score), reverse=True)
    return scored


# ── deck-level advice ────────────────────────────────────────────────────────


def deck_advice(
    measured: list[tuple[str, ContentMetrics]], *, min_pt: float = KAWASAKI_MIN_PT
) -> list[str]:
    """Kawasaki-rule observations about a whole deck.

    Advice, never enforcement: a training deck or a technical appendix has
    every right to break these. The point is that the author chose to, rather
    than finding out when the type came back shrunk.

    Parameters
    ----------
    measured : list of (str, ContentMetrics)
        One ``(title, metrics)`` pair per slide, in deck order.
    min_pt : float, default :data:`KAWASAKI_MIN_PT`
        The font floor the word-count guidance is relative to.

    Returns
    -------
    list of str
        Human-readable notes; empty when the deck already follows the rule.
    """
    notes: list[str] = []
    n = len(measured)
    # Only remark on the slide count when it is well past the ideal. Eleven
    # slides against a target of ten is not worth a line of output; thirty is.
    if n > KAWASAKI_MAX_SLIDES * 1.5:
        notes.append(
            f"{n} slides, against the 10/20/30 ideal of {KAWASAKI_MAX_SLIDES}. "
            "Worth a look if this is a pitch; fine if it is not."
        )

    # A rough per-slide word ceiling at the font floor: more than this and the
    # slide is a document, whatever layout it lands on. Scaled off 30pt/50
    # words so a caller who lowers the floor gets a proportionate ceiling.
    word_ceiling = int(round(50 * (KAWASAKI_MIN_PT / min_pt) ** 2))
    for title, m in measured:
        # 1.5x the ceiling before saying anything: the estimate is approximate
        # and a slide a little over it reads fine.
        if m.word_count > word_ceiling * 1.5:
            notes.append(
                f"{title!r}: ~{m.word_count} words, well above the ~{word_ceiling} "
                f"that sits comfortably at {min_pt:g}pt. Splitting it would help."
            )
        if m.bullet_count > 8:
            notes.append(f"{title!r}: {m.bullet_count} bullets is a lot for one slide.")
    return notes


def summarise_for_prompt(metrics: ContentMetrics) -> str:
    """One line of measured facts about a slide, for an LLM prompt.

    The selector previously described a slide as "features: table, bullets",
    which says what *kind* of content it is but nothing about how much — and
    the amount is what decides whether a layout can hold it.
    """
    parts = [f"{metrics.word_count} words"]
    if metrics.bullet_count:
        parts.append(
            f"{metrics.bullet_count} bullets (longest {metrics.longest_bullet_chars} chars)"
        )
    if metrics.image_count:
        parts.append(f"{metrics.image_count} image(s)")
    if metrics.table_rows:
        parts.append(f"table {metrics.table_rows}x{metrics.table_cols}")
    if metrics.code_lines:
        parts.append(f"{metrics.code_lines} code lines")
    if metrics.is_sparse:
        parts.append("sparse")
    return ", ".join(parts)


def capacity_for_prompt(layout: object, *, min_pt: float = KAWASAKI_MIN_PT) -> str:
    """One line of measured facts about a layout, for an LLM prompt."""
    body = _capacity_for(layout, _BODY_KINDS, min_pt)
    kinds = _kinds(layout)
    pics = sum(1 for k in kinds if k in _PIC_KINDS)
    bits = [f"~{body.chars} chars ({body.lines} lines x {body.chars_per_line}) at {min_pt:g}pt"]
    if pics:
        bits.append(f"{pics} picture slot(s)")
    if not any(k in _TITLE_KINDS for k in kinds):
        bits.append("no title slot")
    return ", ".join(bits)


# ── compositional principles ─────────────────────────────────────────────────
# Occupancy (above) answers "is there the right *amount* of content here?".
# These answer "is it in the right *place*?" -- which is the other half of what
# a designer means by a layout working, and the half a capacity figure cannot
# see. All four are deterministic and cost nothing, which matters: every
# judgement they settle is one the vision model does not have to, and the VLM
# is the slowest and least predictable stage in the pipeline.
#
# Each returns a score in [-1, 1] and a short reason, so a selector can explain
# its ranking in words rather than asserting a number.

#: How close to a rule-of-thirds line a focal element must sit to count as
#: placed on it, as a fraction of the canvas. A twentieth is tight enough to
#: mean something and loose enough to tolerate a designer's optical centring.
THIRDS_TOLERANCE = 0.05

#: How far the centre of mass may drift before the slide reads as lopsided,
#: as a fraction of the half-diagonal. Set above a rule-of-thirds placement
#: (~0.33) on purpose: see :func:`balance` for why that matters.
BALANCE_TOLERANCE = 0.45

#: How close two edges must be to read as deliberately aligned, as a fraction
#: of the canvas.
ALIGNMENT_TOLERANCE = 0.01


def _centre(emu: tuple[int, int, int, int]) -> tuple[float, float]:
    left, top, width, height = emu
    return left + width / 2.0, top + height / 2.0


def _filled_boxes(
    metrics: ContentMetrics, layout: object
) -> list[tuple[str, tuple[int, int, int, int]]]:
    """The placeholders this content would actually occupy.

    An empty placeholder is not part of the composition -- judging balance
    across boxes that will be left blank describes the template, not the
    slide that comes out of it.
    """
    out: list[tuple[str, tuple[int, int, int, int]]] = []
    images_left = metrics.image_count
    has_body = metrics.body_chars or metrics.bullet_count or metrics.table_rows
    for ph in getattr(layout, "placeholders", None) or []:
        kind = getattr(ph, "kind", "") or ""
        emu = getattr(ph, "emu", None)
        if not emu:
            continue
        if kind in _TITLE_KINDS and metrics.title_chars:
            out.append((kind, emu))
        elif kind in _PIC_KINDS and images_left > 0:
            out.append((kind, emu))
            images_left -= 1
        elif kind in _BODY_KINDS and has_body:
            out.append((kind, emu))
    return out


def balance(metrics: ContentMetrics, layout: object, canvas: tuple[int, int]) -> tuple[float, str]:
    """Is the filled content piled into one corner, leaving the rest empty?

    A **defect detector, not a beauty contest**: it returns 0 for anything
    reasonably placed and goes negative only when the area-weighted centre of
    mass is genuinely marooned. Rewarding dead-centre instead would be wrong,
    and provably so -- it put this function in direct conflict with
    :func:`thirds`, which rewards the off-centre placement a designer chooses
    deliberately. Scoring both as preferences meant the two cancelled, and the
    heavier weight silently won: an image sitting exactly on a third ranked
    *below* the same image centred.

    So centring earns nothing here. Only the corner case is called out, which
    is the one that actually looks broken.
    """
    boxes = _filled_boxes(metrics, layout)
    if not boxes:
        return 0.0, ""
    cx, cy = canvas
    total = sum(w * h for _, (_, _, w, h) in boxes)
    if total <= 0 or cx <= 0 or cy <= 0:
        return 0.0, ""
    mx = sum(_centre(e)[0] * e[2] * e[3] for _, e in boxes) / total / cx
    my = sum(_centre(e)[1] * e[2] * e[3] for _, e in boxes) / total / cy
    # Distance from centre, normalised so the far corner scores 1.
    drift = ((mx - 0.5) ** 2 + (my - 0.5) ** 2) ** 0.5 / (0.5 * 2**0.5)
    # A third-placed focal point drifts ~0.33; a corner-piled slide ~0.6+. The
    # threshold sits above the former so deliberate composition is never
    # punished as imbalance.
    if drift <= BALANCE_TOLERANCE:
        return 0.0, ""
    side = "right" if mx > 0.5 else "left"
    vert = "bottom" if my > 0.5 else "top"
    return (
        -min(1.0, (drift - BALANCE_TOLERANCE) / (1.0 - BALANCE_TOLERANCE)),
        f"content would sit {vert}-{side}, leaving the rest empty",
    )


def reading_order(metrics: ContentMetrics, layout: object) -> tuple[float, str]:
    """Does the title come before the body, the way the slide will be read?

    Left-to-right, top-to-bottom. A layout whose body box sits above its title
    is a legitimate design -- a kicker over a headline, say -- but it is the
    wrong host for content whose heading *is* the entry point.
    """
    if not metrics.title_chars:
        return 0.0, ""
    titles = [e for k, e in _filled_boxes(metrics, layout) if k in _TITLE_KINDS]
    bodies = [e for k, e in _filled_boxes(metrics, layout) if k in _BODY_KINDS]
    if not titles or not bodies:
        return 0.0, ""
    t_top = min(e[1] for e in titles)
    b_top = min(e[1] for e in bodies)
    if t_top <= b_top:
        return 0.3, ""
    return -0.5, "the body sits above the title, against the reading order"


def alignment(
    metrics: ContentMetrics, layout: object, canvas: tuple[int, int]
) -> tuple[float, str]:
    """Do the filled boxes share edges, the way a designer would have set them?

    Shared left edges or a shared top is what makes a slide look composed
    rather than assembled. This rewards a layout whose *used* boxes line up --
    which is not automatic, since a layout can be internally tidy and still
    put the two boxes this content needs on unrelated grids.
    """
    boxes = [e for _, e in _filled_boxes(metrics, layout)]
    if len(boxes) < 2:
        return 0.0, ""
    cx = canvas[0]
    if cx <= 0:
        return 0.0, ""
    tol = ALIGNMENT_TOLERANCE * cx
    lefts = [e[0] for e in boxes]
    rights = [e[0] + e[2] for e in boxes]
    aligned = sum(
        1
        for i in range(len(boxes))
        for j in range(i + 1, len(boxes))
        if abs(lefts[i] - lefts[j]) <= tol or abs(rights[i] - rights[j]) <= tol
    )
    pairs = len(boxes) * (len(boxes) - 1) / 2
    return (aligned / pairs if pairs else 0.0), ""


def thirds(metrics: ContentMetrics, layout: object, canvas: tuple[int, int]) -> tuple[float, str]:
    """Does the focal element land near a rule-of-thirds line?

    Only asked about the picture, and only when there is one: the rule is about
    where the eye goes first, and on an image-forward slide that is the image.
    Dead-centre is not penalised -- it is a deliberate choice often enough --
    so this is a bonus for hitting a third, never a penalty for missing it.
    """
    if not metrics.image_count:
        return 0.0, ""
    pics = [e for k, e in _filled_boxes(metrics, layout) if k in _PIC_KINDS]
    if not pics or canvas[0] <= 0 or canvas[1] <= 0:
        return 0.0, ""
    px, py = _centre(pics[0])
    fx, fy = px / canvas[0], py / canvas[1]
    near = min(abs(fx - 1 / 3), abs(fx - 2 / 3)) <= THIRDS_TOLERANCE or (
        min(abs(fy - 1 / 3), abs(fy - 2 / 3)) <= THIRDS_TOLERANCE
    )
    return (0.3, "focal image sits on a third") if near else (0.0, "")


def composition(
    metrics: ContentMetrics, layout: object, canvas: tuple[int, int] | None
) -> tuple[float, list[str]]:
    """Combine the compositional principles into one score and its reasons.

    Weights are deliberately modest relative to the fit score: composition
    ranks layouts that can already host the content, it does not rescue one
    that cannot. Returns ``(0.0, [])`` when the canvas is unknown, so a
    template whose size could not be read simply falls back to fit alone.
    """
    if not canvas:
        return 0.0, []
    checks = (
        (balance(metrics, layout, canvas), 0.20),
        (reading_order(metrics, layout), 0.15),
        (alignment(metrics, layout, canvas), 0.10),
        (thirds(metrics, layout, canvas), 0.15),
    )
    reasons: list[str] = []
    total = 0.0
    for (score, reason), weight in checks:
        total += score * weight
        if reason:
            reasons.append(reason)
    return total, reasons
