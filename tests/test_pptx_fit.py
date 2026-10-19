"""Tests for the content-to-layout fit computation (:mod:`md2star.pptx_fit`).

Offline and model-free: layouts are tiny synthetic stand-ins with real EMU
geometry, so the arithmetic is exercised without a designer template, a
rendering engine or an LLM.

What these pin down, in order of importance:

1. **A refusal is structural, never "too much text".** 10/20/30 is an ideal, so
   a slide that overruns the font target is scored down and reported, not
   rejected. The only hard refusals are "nowhere to put this image" and
   "nowhere to put this table".
2. **A caption's worth of text does not disqualify a photo layout.** One image
   and a line under it is the target deck, and the line can ride in the title.
3. **Capacity comes from geometry**, so a bigger box holds more and a smaller
   font floor holds more still.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from md2star.pptx_fit import (
    CAPTION_CHARS,
    KAWASAKI_MIN_PT,
    TARGET_OCCUPANCY,
    ContentMetrics,
    deck_advice,
    evaluate,
    measure,
    placeholder_capacity,
    rank,
    summarise_for_prompt,
)

# A 16:9 deck, the size every modern template uses.
DECK_W, DECK_H = 9144000, 5143500


def box(fx: float, fy: float, fw: float, fh: float) -> tuple[int, int, int, int]:
    """A placeholder box given as fractions of the slide."""
    return (int(DECK_W * fx), int(DECK_H * fy), int(DECK_W * fw), int(DECK_H * fh))


@dataclass
class FakePlaceholder:
    idx: int
    kind: str
    emu: tuple[int, int, int, int] | None = None


@dataclass
class FakeLayout:
    name: str
    placeholders: list[FakePlaceholder] = field(default_factory=list)


TITLE_ONLY = FakeLayout("TITLE_ONLY", [FakePlaceholder(0, "title", box(0.1, 0.35, 0.8, 0.3))])
PHOTO_HERO = FakeLayout(
    "PHOTO_HERO",
    [
        FakePlaceholder(0, "title", box(0.05, 0.05, 0.9, 0.15)),
        FakePlaceholder(1, "pic", box(0.05, 0.25, 0.9, 0.65)),
    ],
)
TITLE_BODY = FakeLayout(
    "TITLE_BODY",
    [
        FakePlaceholder(0, "title", box(0.05, 0.05, 0.9, 0.15)),
        FakePlaceholder(1, "body", box(0.05, 0.25, 0.9, 0.65)),
    ],
)
PIC_CAPTION = FakeLayout(
    "PIC_CAPTION",
    [
        FakePlaceholder(0, "title", box(0.05, 0.05, 0.9, 0.12)),
        FakePlaceholder(1, "pic", box(0.05, 0.2, 0.55, 0.7)),
        FakePlaceholder(2, "body", box(0.65, 0.2, 0.3, 0.7)),
    ],
)
ALL_LAYOUTS = [TITLE_ONLY, PHOTO_HERO, TITLE_BODY, PIC_CAPTION]


def _md(*lines: str) -> str:
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# measuring content
# ---------------------------------------------------------------------------


def test_measure_counts_what_a_reader_sees_not_markup() -> None:
    m = measure("Results", _md("# Results", "", "- **one**", "- `two`"))
    assert m.bullet_count == 2
    # Bullet markers, bold and backticks are markup; they must not inflate the
    # character count the capacity check is compared against.
    assert m.body_chars == len("one two")


def test_measure_separates_table_structure_from_content() -> None:
    m = measure("T", _md("# T", "", "| a | b |", "|---|---|", "| 1 | 2 |", "| 3 | 4 |"))
    # The |---| separator is structure, not a data row.
    assert m.table_rows == 3
    assert m.table_cols == 2


def test_measure_counts_fence_lines_without_counting_their_text() -> None:
    m = measure("Code", _md("# Code", "", "```python", "x = 1", "y = 2", "```"))
    assert m.code_lines == 2
    assert m.body_chars == 0


def test_a_table_is_never_sparse_however_few_words_surround_it() -> None:
    """Counting only prose would have called thirteen rows of figures sparse."""
    m = measure("N", _md("# N", "", "| a |", "|---|", *[f"| {i} |" for i in range(13)]))
    assert m.word_count == 0
    assert not m.is_sparse


def test_one_image_and_a_line_is_sparse() -> None:
    m = measure("Reach", _md("# Reach", "", "![map](m.png)", "", "Everywhere that matters."))
    assert m.image_count == 1
    assert m.is_sparse


# ---------------------------------------------------------------------------
# measuring the container
# ---------------------------------------------------------------------------


def test_capacity_scales_with_the_box() -> None:
    small = placeholder_capacity(box(0, 0, 0.3, 0.3))
    large = placeholder_capacity(box(0, 0, 0.9, 0.65))
    assert large.chars > small.chars > 0


def test_capacity_grows_as_the_font_target_drops() -> None:
    """Smaller type holds more text -- that is why a floor is needed at all."""
    at_30 = placeholder_capacity(box(0, 0, 0.9, 0.65), min_pt=30)
    at_18 = placeholder_capacity(box(0, 0, 0.9, 0.65), min_pt=18)
    assert at_18.chars > at_30.chars


@pytest.mark.parametrize("bad", [None, (0, 0, 0, 0), (0, 0, -1, 100)])
def test_capacity_of_a_degenerate_box_is_zero_not_an_error(bad) -> None:
    assert placeholder_capacity(bad).chars == 0


# ---------------------------------------------------------------------------
# the verdict: what is refused, and what is merely reported
# ---------------------------------------------------------------------------


def test_an_image_with_nowhere_to_go_is_refused() -> None:
    """Structural: no font size makes a picture fit a layout without a pic box."""
    m = measure("Reach", _md("# Reach", "", "![map](m.png)"))
    assert evaluate(m, TITLE_BODY).fits is False


def test_a_table_with_no_body_placeholder_is_refused() -> None:
    """A title-only layout has no laid-out region for thirteen rows.

    Regression: the structural charge is scaled by chars-per-line, which is 0
    for a title-only layout, so the table multiplied out to nothing and the
    layout looked like a perfect fit.
    """
    m = measure("N", _md("# N", "", "| a |", "|---|", *[f"| {i} |" for i in range(13)]))
    report = evaluate(m, TITLE_ONLY)
    assert report.fits is False
    assert "no body or table placeholder" in " ".join(report.reasons)


def test_too_much_text_is_reported_not_refused() -> None:
    """The 10/20/30 font target is an ideal; a dense slide is still a slide."""
    m = measure(
        "Roadmap", _md("# Roadmap", "", *[f"- Phase {i}: " + "word " * 12 for i in range(8)])
    )
    report = evaluate(m, TITLE_BODY)
    assert report.fits is True, "overrunning the font target must not disqualify"
    assert report.overruns is True
    assert report.overflow_chars > 0


def test_strict_mode_turns_an_overrun_into_a_refusal() -> None:
    """For a caller who does want the rule enforced."""
    m = measure(
        "Roadmap", _md("# Roadmap", "", *[f"- Phase {i}: " + "word " * 12 for i in range(8)])
    )
    assert evaluate(m, TITLE_BODY, strict=True).fits is False


def test_an_overrun_reports_the_size_that_would_actually_fit() -> None:
    """ "This is a 22pt slide" is actionable; "does not fit" is not."""
    m = measure(
        "Roadmap", _md("# Roadmap", "", *[f"- Phase {i}: " + "word " * 12 for i in range(8)])
    )
    report = evaluate(m, TITLE_BODY)
    assert 0 < report.implied_pt < KAWASAKI_MIN_PT


def test_a_caption_rides_in_a_title_only_layout() -> None:
    """One image and a line under it is the target deck, not an edge case.

    Rejecting the template's best photo layout over four words of caption
    would be exactly backwards.
    """
    m = measure("Reach", _md("# Reach", "", "![map](m.png)", "", "Everywhere that matters."))
    report = evaluate(m, PHOTO_HERO)
    assert report.fits is True
    assert m.body_chars <= CAPTION_CHARS


def test_more_than_a_caption_without_a_body_box_is_refused() -> None:
    m = measure("Reach", _md("# Reach", "", "![map](m.png)", "", "word " * 80))
    assert evaluate(m, PHOTO_HERO).fits is False


# ---------------------------------------------------------------------------
# ranking: does the best layout actually win?
# ---------------------------------------------------------------------------


def _winner(markdown: str, title: str = "T") -> str:
    return rank(measure(title, markdown), ALL_LAYOUTS)[0][0].name


def test_one_image_and_few_words_picks_an_image_layout() -> None:
    winner = _winner(_md("# Reach", "", "![map](m.png)", "", "Everywhere that matters."))
    assert winner in {"PIC_CAPTION", "PHOTO_HERO"}


def test_a_big_statement_picks_the_layout_with_no_empty_body_box() -> None:
    """{.big} is a structural request: give the headline the stage alone."""
    assert _winner(_md("# 10x {.big}")) == "TITLE_ONLY"


def test_prose_picks_a_body_layout() -> None:
    assert _winner(_md("# Why", "", "word " * 40)) in {"TITLE_BODY", "PIC_CAPTION"}


def test_ranking_never_returns_an_empty_list_for_a_dense_slide() -> None:
    """A deck that overruns everywhere must still get a best available choice."""
    m = measure("Dense", _md("# Dense", "", "word " * 400))
    ordered = rank(m, ALL_LAYOUTS)
    assert ordered
    assert ordered[0][1].fits is True


def test_fitting_layouts_sort_ahead_of_refused_ones() -> None:
    m = measure("Reach", _md("# Reach", "", "![map](m.png)"))
    ordered = rank(m, ALL_LAYOUTS)
    fits = [r.fits for _, r in ordered]
    assert fits == sorted(fits, reverse=True)


def test_an_empty_picture_box_costs_a_text_only_slide() -> None:
    """A picture slot with nothing in it reads as a hole in the slide."""
    m = measure("Why", _md("# Why", "", "word " * 20))
    assert evaluate(m, TITLE_BODY).score > evaluate(m, PIC_CAPTION).score


# ---------------------------------------------------------------------------
# occupancy
# ---------------------------------------------------------------------------


def test_a_comfortable_slide_scores_above_an_almost_empty_one() -> None:
    """SlideGen's occupancy term: neither abandoned nor crammed."""
    roomy = ContentMetrics(
        body_chars=int(placeholder_capacity(box(0.05, 0.25, 0.9, 0.65)).chars * TARGET_OCCUPANCY)
    )
    sparse = ContentMetrics(body_chars=5)
    assert evaluate(roomy, TITLE_BODY).score > evaluate(sparse, TITLE_BODY).score


# ---------------------------------------------------------------------------
# advice, which must stay advice
# ---------------------------------------------------------------------------


def test_a_ten_slide_deck_draws_no_remarks() -> None:
    measured = [(f"S{i}", measure(f"S{i}", _md(f"# S{i}", "", "word " * 10))) for i in range(10)]
    assert deck_advice(measured) == []


def test_eleven_slides_is_not_worth_a_remark() -> None:
    """The ideal is ten; one over is noise, not a finding."""
    measured = [(f"S{i}", measure(f"S{i}", _md(f"# S{i}", "", "word " * 10))) for i in range(11)]
    assert not any("slides" in n for n in deck_advice(measured))


def test_a_thirty_slide_deck_does_draw_one() -> None:
    measured = [(f"S{i}", measure(f"S{i}", _md(f"# S{i}", "", "word " * 10))) for i in range(30)]
    assert any("10/20/30" in n for n in deck_advice(measured))


def test_a_wall_of_text_slide_is_flagged() -> None:
    measured = [("Wall", measure("Wall", _md("# Wall", "", "word " * 300)))]
    notes = deck_advice(measured)
    assert any("Wall" in n and "words" in n for n in notes)


# ---------------------------------------------------------------------------
# prompt surfaces
# ---------------------------------------------------------------------------


def test_the_prompt_summary_carries_quantities_not_just_kinds() -> None:
    """The selector used to see "features: table, bullets" and nothing more.

    How *much* content there is decides whether a layout can hold it, so the
    numbers have to reach the model.
    """
    m = measure("N", _md("# N", "", "- a", "- b", "| x | y |", "|---|---|", "| 1 | 2 |"))
    summary = summarise_for_prompt(m)
    assert "2 bullets" in summary
    assert "table 2x2" in summary


# ---------------------------------------------------------------------------
# integration with the real selector
# ---------------------------------------------------------------------------
# select_layouts has three paths into a decision, and geometry participates in
# all three: it decides alone when there is no model, it overrules a model that
# names an impossible layout, and it stays out of the way when the model's pick
# is sound.


def _real_catalog():
    from md2star.pptx_layout import LayoutInfo, Placeholder

    return [
        LayoutInfo(
            name="BIG_STATEMENT",
            placeholders=[Placeholder(0, "title", box(0.1, 0.35, 0.8, 0.3))],
            archetype="big-statement",
        ),
        LayoutInfo(
            name="PHOTO_HERO",
            placeholders=[
                Placeholder(0, "title", box(0.05, 0.05, 0.9, 0.15)),
                Placeholder(1, "pic", box(0.05, 0.25, 0.9, 0.65)),
            ],
            archetype="photo-hero",
        ),
        LayoutInfo(
            name="TITLE_BODY",
            placeholders=[
                Placeholder(0, "title", box(0.05, 0.05, 0.9, 0.15)),
                Placeholder(1, "body", box(0.05, 0.25, 0.9, 0.65)),
            ],
            archetype="bulleted-content",
        ),
    ]


def _image_slide():
    from md2star.pptx_layout import Slide

    return [
        Slide(
            index=0,
            title="Our reach",
            body=_md("# Our reach", "", "![map](m.png)", "", "Short."),
            features=["image"],
        )
    ]


def test_geometry_decides_when_no_model_is_available() -> None:
    """The common case offline, and now the better of the two fallbacks.

    The old path guessed an archetype from five regex rules, which cannot know
    whether a layout has anywhere to put the image.
    """
    from md2star.pptx_layout import select_layouts

    slides = _image_slide()
    select_layouts(slides, _real_catalog(), chat=lambda *a: None)
    assert slides[0].chosen_layout == "PHOTO_HERO"
    assert "geometric" in slides[0].chosen_why


def test_geometry_overrules_a_model_that_names_an_impossible_layout() -> None:
    """A preference that is checkable beats one that is not."""
    from md2star.pptx_layout import select_layouts

    slides = _image_slide()
    select_layouts(
        slides,
        _real_catalog(),
        chat=lambda *a: {
            "choices": [
                {"index": 0, "layout_name": "TITLE_BODY", "confidence": 0.9, "why": "sounds right"}
            ]
        },
    )
    assert slides[0].chosen_layout == "PHOTO_HERO"
    assert "overrode" in slides[0].chosen_why


def test_a_sound_model_pick_is_left_alone() -> None:
    """Geometry is a floor on plausibility, not a second opinion on taste."""
    from md2star.pptx_layout import select_layouts

    slides = _image_slide()
    select_layouts(
        slides,
        _real_catalog(),
        chat=lambda *a: {
            "choices": [
                {"index": 0, "layout_name": "PHOTO_HERO", "confidence": 0.9, "why": "image slide"}
            ]
        },
    )
    assert slides[0].chosen_layout == "PHOTO_HERO"
    assert slides[0].chosen_why == "image slide"


def test_the_prompt_states_each_layout_capacity() -> None:
    """The model could not previously guess either side's dimensions."""
    from md2star.pptx_layout import select_layouts

    seen = {}

    def chat(prompt, img, schema):
        seen["prompt"] = prompt
        return None

    select_layouts(_image_slide(), _real_catalog(), chat=chat)
    assert "holds ~" in seen["prompt"]
    assert "at 30pt" in seen["prompt"]
    assert "cannot hold it:" in seen["prompt"]


def test_every_slide_still_gets_a_layout() -> None:
    """Whatever happens, the assembler must never meet an unassigned slide."""
    from md2star.pptx_layout import Slide, select_layouts

    slides = [
        Slide(index=0, title="A", body=_md("# A", "", "word " * 500), features=[]),
        Slide(index=1, title="B", body=_md("# B"), features=[]),
    ]
    select_layouts(slides, _real_catalog(), chat=lambda *a: None)
    assert all(s.chosen_layout for s in slides)


# ---------------------------------------------------------------------------
# compositional principles
# ---------------------------------------------------------------------------
# Occupancy asks "is there the right amount of content here?"; these ask "is it
# in the right place?" -- the other half of what a designer means by a layout
# working, and the half a capacity figure cannot see.

CANVAS = (DECK_W, DECK_H)


def _layout(*boxes: tuple[str, tuple[int, int, int, int]]) -> FakeLayout:
    return FakeLayout("L", [FakePlaceholder(i, k, e) for i, (k, e) in enumerate(boxes)])


def test_content_piled_into_a_corner_is_penalised() -> None:
    corner = _layout(("pic", box(0.02, 0.02, 0.2, 0.2)))
    report = evaluate(measure("", "![x](x.png)"), corner, canvas=CANVAS)
    assert report.composition < 0
    assert any("leaving the rest empty" in r for r in report.reasons)


def test_a_body_above_its_title_is_penalised() -> None:
    """A legitimate design, but the wrong host for content whose heading leads."""
    inverted = _layout(("title", box(0.05, 0.75, 0.9, 0.15)), ("body", box(0.05, 0.05, 0.9, 0.6)))
    normal = _layout(("title", box(0.05, 0.05, 0.9, 0.15)), ("body", box(0.05, 0.25, 0.9, 0.6)))
    m = measure("Title", _md("# Title", "", "word " * 20))
    assert evaluate(m, normal, canvas=CANVAS).score > evaluate(m, inverted, canvas=CANVAS).score
    assert any(
        "against the reading order" in r for r in evaluate(m, inverted, canvas=CANVAS).reasons
    )


def test_a_focal_image_on_a_third_beats_the_same_image_centred() -> None:
    """Regression: balance and thirds used to contradict each other.

    Balance rewarded centring, thirds rewarded the off-centre placement a
    designer chooses deliberately. The two cancelled and the heavier weight
    won, so an image sitting exactly on a third ranked *below* the same image
    centred -- the opposite of the principle being applied. Balance is now a
    defect detector that scores 0 for anything reasonably placed.
    """
    third = _layout(("pic", box(1 / 3 - 0.15, 0.25, 0.3, 0.5)))
    centred = _layout(("pic", box(0.35, 0.25, 0.3, 0.5)))
    m = measure("", "![x](x.png)")
    assert evaluate(m, third, canvas=CANVAS).score > evaluate(m, centred, canvas=CANVAS).score


def test_centring_is_not_rewarded_only_marooning_is_punished() -> None:
    """Otherwise the two principles fight, as above."""
    from md2star.pptx_fit import balance

    centred = _layout(("body", box(0.3, 0.3, 0.4, 0.4)))
    score, reason = balance(measure("", "word " * 10), centred, CANVAS)
    assert score == 0.0
    assert reason == ""


def test_empty_placeholders_are_not_part_of_the_composition() -> None:
    """Judging balance across boxes that stay blank describes the template.

    A text-only slide on a layout with a big picture box must be judged on
    where its *text* lands, not on the centre of mass of a box nothing fills.
    """
    from md2star.pptx_fit import _filled_boxes

    lay = _layout(("body", box(0.05, 0.05, 0.4, 0.4)), ("pic", box(0.55, 0.55, 0.4, 0.4)))
    filled = _filled_boxes(measure("", "word " * 10), lay)
    assert [k for k, _ in filled] == ["body"]


def test_composition_is_skipped_when_the_canvas_is_unknown() -> None:
    """A template whose size could not be read falls back to fit alone."""
    lay = _layout(("title", box(0.05, 0.05, 0.9, 0.15)), ("body", box(0.05, 0.25, 0.9, 0.6)))
    report = evaluate(measure("T", _md("# T", "", "word " * 20)), lay, canvas=None)
    assert report.composition == 0.0


def test_composition_never_rescues_a_layout_that_cannot_host_the_content() -> None:
    """It ranks the possible; it does not make the impossible possible."""
    no_pic = _layout(("title", box(0.05, 0.05, 0.9, 0.15)), ("body", box(0.05, 0.25, 0.9, 0.6)))
    report = evaluate(measure("T", _md("# T", "", "![x](x.png)")), no_pic, canvas=CANVAS)
    assert report.fits is False
    assert report.score == 0.0


# ---------------------------------------------------------------------------
# the feedback edge: the loop can move a slide, not only patch it
# ---------------------------------------------------------------------------
# font_delta / bullets / img_grow all assume the layout was right and the
# content merely needs trimming. When the verdict is `too_empty`, or overflow
# that -4pt will not close, that assumption is itself the error: the slide is
# somewhere it should never have been put. pptx_assemble's own comment said so
# -- those verdicts "need a layout swap, not a font/bullet tweak".


def _ranked_slide(body: str, layouts: list):
    from md2star.pptx_layout import Slide

    s = Slide(index=0, title="T", body=body)
    s.fit_ranked = rank(measure(s.title, s.body), layouts)
    return s


def _real_layout(name: str, *boxes):
    from md2star.pptx_layout import LayoutInfo, Placeholder

    return LayoutInfo(
        name=name, placeholders=[Placeholder(i, k, e) for i, (k, e) in enumerate(boxes)]
    )


TIGHT = _real_layout(
    "TIGHT", ("title", box(0.05, 0.05, 0.9, 0.1)), ("body", box(0.05, 0.2, 0.3, 0.3))
)
ROOMY = _real_layout(
    "ROOMY", ("title", box(0.05, 0.05, 0.9, 0.15)), ("body", box(0.05, 0.25, 0.9, 0.65))
)
MID = _real_layout(
    "MID", ("title", box(0.05, 0.05, 0.9, 0.15)), ("body", box(0.05, 0.25, 0.5, 0.6))
)


@pytest.fixture
def reselect():
    """The loop's layout swap, which lives in the assembler.

    Importing it pulls in ``python-pptx`` — the opt-in ``[pptx]`` extra — even
    though the swap itself is pure ranking arithmetic. Reaching it through a
    fixture means a checkout without that extra *skips* these five tests
    instead of erroring on the import, exactly like tests/test_pptx_assemble.py.
    """
    pytest.importorskip("pptx")
    from md2star.pptx_assemble import _reselect

    return _reselect


def test_the_loop_moves_a_slide_off_a_layout_that_cannot_carry_it(reselect) -> None:
    s = _ranked_slide(_md("# T", "", "word " * 25), [TIGHT, ROOMY, MID])
    s.chosen_layout = "TIGHT"  # as if a model insisted on it
    assert reselect(s) == "ROOMY"


def test_a_layout_already_rejected_is_not_offered_again(reselect) -> None:
    """Otherwise the loop ping-pongs between two layouts until it runs out."""
    s = _ranked_slide(_md("# T", "", "word " * 25), [TIGHT, ROOMY, MID])
    s.chosen_layout = "ROOMY"
    s.tried_layouts = ["TIGHT"]
    assert reselect(s) == "MID"


def test_exhausting_the_options_keeps_the_current_pick(reselect) -> None:
    """None means "report it", not "break the deck"."""
    s = _ranked_slide(_md("# T", "", "word " * 25), [TIGHT, ROOMY, MID])
    s.chosen_layout = "MID"
    s.tried_layouts = ["TIGHT", "ROOMY"]
    assert reselect(s) is None


def test_a_slide_with_no_ranking_is_left_alone(reselect) -> None:
    """Selection may have run without geometry (an older call path)."""
    from md2star.pptx_layout import Slide

    s = Slide(index=0, title="T", body="# T")
    s.chosen_layout = "TIGHT"
    assert reselect(s) is None


def test_the_loop_never_moves_a_slide_onto_an_overrunning_layout(reselect) -> None:
    """Swapping one bad host for another is not progress."""
    s = _ranked_slide(_md("# T", "", "word " * 25), [TIGHT, ROOMY])
    s.chosen_layout = "ROOMY"
    s.tried_layouts = []
    # TIGHT overruns for this content, so it is not a destination.
    assert reselect(s) is None


# ---------------------------------------------------------------------------
# aspect matching — the one principle that touches the disk
# ---------------------------------------------------------------------------
# A count cannot tell a panorama from a portrait, and those two want opposite
# layouts. SlideGen states the rule (wide images to image-top, "tall or square
# images receive half-and-half"); comparing aspects produces that routing on
# its own, and keeps working for shapes nobody wrote a rule for.


@pytest.fixture
def images(tmp_path):
    """Four real images, header-readable, of deliberately different shapes."""
    from PIL import Image

    for name, size in {
        "pano": (1920, 480),
        "wide": (1600, 900),
        "square": (800, 800),
        "tall": (600, 1400),
    }.items():
        Image.new("RGB", size, "gray").save(tmp_path / f"{name}.png")
    return tmp_path


IMAGE_TOP = _layout(("pic", box(0.05, 0.05, 0.9, 0.35)))
HALF_HALF = _layout(("pic", box(0.05, 0.1, 0.42, 0.8)))


def test_a_panorama_prefers_the_image_top_layout(images) -> None:
    from md2star.pptx_fit import aspect_match

    m = measure("", "![x](pano.png)")
    top, _ = aspect_match(m, IMAGE_TOP, base_dir=images)
    half, _ = aspect_match(m, HALF_HALF, base_dir=images)
    assert top > half


@pytest.mark.parametrize("name", ["square", "tall"])
def test_square_and_tall_images_prefer_half_and_half(images, name: str) -> None:
    from md2star.pptx_fit import aspect_match

    m = measure("", f"![x]({name}.png)")
    top, _ = aspect_match(m, IMAGE_TOP, base_dir=images)
    half, _ = aspect_match(m, HALF_HALF, base_dir=images)
    assert half > top


def test_a_badly_mismatched_image_says_what_will_happen(images) -> None:
    """ "It will be letterboxed or cropped" is actionable; a number is not."""
    from md2star.pptx_fit import aspect_match

    score, reason = aspect_match(measure("", "![x](tall.png)"), IMAGE_TOP, base_dir=images)
    assert score < 0
    assert "letterboxed or cropped" in reason


def test_the_worst_pairing_decides(images) -> None:
    """One badly letterboxed image spoils the slide, however well others sit."""
    from md2star.pptx_fit import aspect_match

    two_boxes = _layout(
        ("pic", box(0.05, 0.05, 0.9, 0.35)),  # wide box, suits the panorama
        ("pic", box(0.05, 0.5, 0.9, 0.35)),  # wide box, ruinous for the tall one
    )
    both = measure("", "![a](pano.png)\n![b](tall.png)")
    worst, reason = aspect_match(both, two_boxes, base_dir=images)
    only_good, _ = aspect_match(measure("", "![a](pano.png)"), two_boxes, base_dir=images)
    assert worst < only_good
    assert "tall.png" in reason


# --- the no-signal cases, which must never be read as a bad signal ---------


def test_a_remote_image_is_skipped_not_penalised(images) -> None:
    """Selection must not do network I/O: a choice that hangs on a dead host
    is worse than one made without the aspect."""
    from md2star.pptx_fit import aspect_match

    m = measure("", "![x](https://example.com/photo.png)")
    assert aspect_match(m, IMAGE_TOP, base_dir=images) == (0.0, "")


def test_a_missing_file_is_skipped(images) -> None:
    from md2star.pptx_fit import aspect_match

    m = measure("", "![x](nope.png)")
    assert aspect_match(m, IMAGE_TOP, base_dir=images) == (0.0, "")


def test_no_base_dir_means_no_signal(images) -> None:
    """Otherwise every deck keeping images elsewhere would be penalised."""
    from md2star.pptx_fit import aspect_match

    m = measure("", "![x](pano.png)")
    assert aspect_match(m, IMAGE_TOP, base_dir=None) == (0.0, "")


def test_a_layout_with_no_picture_box_is_not_judged_on_aspect(images) -> None:
    from md2star.pptx_fit import aspect_match

    text_only = _layout(("body", box(0.05, 0.25, 0.9, 0.6)))
    m = measure("", "![x](pano.png)")
    assert aspect_match(m, text_only, base_dir=images) == (0.0, "")


def test_an_unreadable_file_is_skipped_not_raised(images) -> None:
    """A truncated download must not take a conversion down with it."""
    from md2star.pptx_fit import aspect_match

    (images / "broken.png").write_bytes(b"not an image")
    m = measure("", "![x](broken.png)")
    assert aspect_match(m, IMAGE_TOP, base_dir=images) == (0.0, "")


# --- path parsing, which the aspect check depends on ----------------------


def test_bracketed_paths_with_spaces_survive() -> None:
    """`<tall one.jpg>` used to truncate at the space, yielding "tall"."""
    m = measure("T", '# T\n\n![a](pics/w.png)\n![b](<tall one.jpg> "caption")\n![c](p.png "t")')
    assert m.image_paths == ["pics/w.png", "tall one.jpg", "p.png"]
