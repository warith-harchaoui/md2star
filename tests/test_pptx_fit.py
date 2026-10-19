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
