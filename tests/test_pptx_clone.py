"""Seam E: cloning the designer's own example page instead of a bare layout.

The seam's whole value is that it brings the designer's decorative shapes
along, and its whole risk is that it might bring the designer's *words* along
with them. So the tests come in two halves:

* **what must survive** — the accent bar, the logo, the "01" of a numbered
  step, the master's bullet glyph, the picture's slot and its stacking order;
* **what must not** — every line of filler text, their stand-in photo (both
  on the slide *and* inside the saved file), and any page the seam cannot
  honestly carry, which must be declined rather than half-filled.

The designer template is synthesised here, page by page, so the suite stays
offline and model-free: no LibreOffice, no Ollama, no network, and nothing
checked in but the code that builds it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")
PIL = pytest.importorskip("PIL")

from pptx.enum.shapes import MSO_SHAPE  # noqa: E402
from pptx.oxml import parse_xml  # noqa: E402
from pptx.oxml.ns import nsdecls, qn  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

from md2star import pptx_assemble as pa  # noqa: E402
from md2star import pptx_audit as au  # noqa: E402
from md2star import pptx_clone as pc  # noqa: E402
from md2star import pptx_layout as pl  # noqa: E402

#: Every line the designer wrote into the synthetic template. Nothing matching
#: this may appear in a built deck — the single property this module exists for.
FILLER = ("DESIGNER", "FILLER", "lorem", "Subtitle filler", "Designer column")

#: A group of shapes with words inside it. python-pptx can read groups but not
#: create them, and the rule that a group with the designer's text in it
#: disqualifies its whole page is worth pinning, so here is the XML.
_GROUP_WITH_WORDS = """
<p:grpSp %s>
  <p:nvGrpSpPr>
    <p:cNvPr id="90" name="Group 90"/><p:cNvGrpSpPr/><p:nvPr/>
  </p:nvGrpSpPr>
  <p:grpSpPr>
    <a:xfrm>
      <a:off x="457200" y="457200"/><a:ext cx="914400" cy="914400"/>
      <a:chOff x="457200" y="457200"/><a:chExt cx="914400" cy="914400"/>
    </a:xfrm>
  </p:grpSpPr>
  <p:sp>
    <p:nvSpPr>
      <p:cNvPr id="91" name="Grouped 91"/><p:cNvSpPr txBox="1"/><p:nvPr/>
    </p:nvSpPr>
    <p:spPr>
      <a:xfrm>
        <a:off x="457200" y="457200"/><a:ext cx="914400" cy="914400"/>
      </a:xfrm>
      <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    </p:spPr>
    <p:txBody>
      <a:bodyPr/><a:lstStyle/>
      <a:p><a:r><a:t>DESIGNER words inside a group</a:t></a:r></a:p>
    </p:txBody>
  </p:sp>
</p:grpSp>
""" % nsdecls("p", "a")


def _add_group_with_words(slide) -> None:
    slide.shapes._spTree.append(parse_xml(_GROUP_WITH_WORDS))


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A directory with the images the template and the deck both reference."""
    from PIL import Image

    Image.new("RGB", (1600, 900), (20, 60, 120)).save(tmp_path / "chart.png")
    Image.new("RGB", (64, 64), (200, 30, 30)).save(tmp_path / "logo.png")
    Image.new("RGB", (1200, 800), (90, 90, 90)).save(tmp_path / "stock.png")
    return tmp_path


@pytest.fixture
def designer(workspace: Path) -> Path:
    """A synthetic designer template: six example pages, one per situation.

    1. ``Title Slide`` — a cover with an accent bar and a small logo.
    2. ``Title and Content`` — bullets, plus an "01" chevron ornament.
    3. ``Title Only`` — three equal columns (a steps design).
    4. ``Picture with Caption`` — a stand-in photo, a caption, and a text
       shape *after* the picture in the tree, so stacking order is testable.
    5. ``Section Header`` — a divider, title only.
    6. ``Two Content`` — a page with a table on it, which no replacement can
       restate.
    7. ``Title and Content`` again — a *second* example of one layout, so the
       eyeball loop has another composition to move a slide onto.
    8. ``Blank`` — a split design: a lead-in panel left, two statements
       stacked right, which is where reading order stops being ``(top, left)``.
    """
    prs = pptx.Presentation()
    layouts = {layout.name: layout for m in prs.slide_masters for layout in m.slide_layouts}

    cover = prs.slides.add_slide(layouts["Title Slide"])
    cover.shapes.title.text = "DESIGNER COVER FILLER"
    for ph in cover.placeholders:
        # By element, not by proxy: python-pptx hands out a fresh shape object
        # on every access, so `ph is not cover.shapes.title` is always true and
        # would overwrite the title with the subtitle's filler.
        if ph.element is not cover.shapes.title.element:
            ph.text_frame.text = "Subtitle filler by the designer"
    cover.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.5), Inches(5.0), Inches(3.0), Inches(0.12))
    cover.shapes.add_picture(str(workspace / "logo.png"), Inches(8.5), Inches(0.3), Inches(0.5))

    bullets = prs.slides.add_slide(layouts["Title and Content"])
    bullets.shapes.title.text = "DESIGNER BULLETS FILLER"
    body = bullets.placeholders[1].text_frame
    body.text = "Filler bullet one"
    for line in ("Filler bullet two", "Filler bullet three"):
        body.add_paragraph().text = line
    chevron = bullets.shapes.add_shape(
        MSO_SHAPE.CHEVRON, Inches(8.0), Inches(1.0), Inches(1.0), Inches(0.6)
    )
    chevron.text_frame.text = "01"

    steps = prs.slides.add_slide(layouts["Title Only"])
    steps.shapes.title.text = "DESIGNER THREE STEPS"
    for column in range(3):
        box = steps.shapes.add_textbox(
            Inches(0.5 + column * 3.1), Inches(2.5), Inches(2.9), Inches(2.0)
        )
        box.text_frame.text = f"Designer column filler {column + 1}"

    picture = prs.slides.add_slide(layouts["Picture with Caption"])
    picture.shapes.title.text = "DESIGNER PICTURE FILLER"
    picture.shapes.add_picture(
        str(workspace / "stock.png"), Inches(1.0), Inches(1.8), Inches(5.0), Inches(3.3)
    )
    caption = picture.shapes.add_textbox(Inches(6.3), Inches(1.8), Inches(3.2), Inches(1.0))
    caption.text_frame.text = "Designer caption lorem ipsum"

    divider = prs.slides.add_slide(layouts["Section Header"])
    divider.shapes.title.text = "DESIGNER SECTION FILLER"

    tabled = prs.slides.add_slide(layouts["Two Content"])
    tabled.shapes.title.text = "DESIGNER TABLE FILLER"
    tabled.shapes.add_table(2, 2, Inches(1.0), Inches(2.0), Inches(6.0), Inches(2.0))

    # 7. A split design, in the proportions a real one has: a lead-in panel on
    #    the left and two statements stacked on the right. Sorting its frames
    #    by (top, left) interleaves the halves, which is the defect a live run
    #    on a designer template surfaced.
    # 8. A SECOND example of the bullets layout, so one layout offers the
    #    eyeball loop a choice of compositions — which is the whole point of
    #    its page-move fix, and what `rep_page` (always the first) cannot see.
    second = prs.slides.add_slide(layouts["Title and Content"])
    second.shapes.title.text = "DESIGNER SECOND BULLETS FILLER"
    second_body = second.placeholders[1].text_frame
    second_body.text = "Filler alternative one"
    second_body.add_paragraph().text = "Filler alternative two"

    split = prs.slides.add_slide(layouts["Blank"])
    heading = split.shapes.add_textbox(Inches(0.3), Inches(0.3), Inches(2.6), Inches(0.6))
    heading.text_frame.text = "DESIGNER SPLIT FILLER"
    heading.text_frame.paragraphs[0].runs[0].font.size = Pt(28)
    lead = split.shapes.add_textbox(Inches(0.4), Inches(2.0), Inches(2.4), Inches(1.3))
    lead.text_frame.text = "Designer column filler lead"
    for row, top in enumerate((1.8, 3.2)):
        statement = split.shapes.add_textbox(Inches(3.6), Inches(top), Inches(4.2), Inches(0.7))
        statement.text_frame.text = f"Designer column filler right {row + 1}"

    out = workspace / "designer.pptx"
    prs.save(str(out))
    return out


#: Markdown exercising each branch: a cover, bullets, a three-bullet steps
#: slide, a picture, a closing divider.
_SRC = """\
---
title: Quarterly Review
---

# Quarterly Review

***

## Where we stand

- Revenue up 18% year on year
- Churn flat at 2.1%
- Pipeline doubled

::: notes
Provisional until the audit closes.
:::

***

## Three steps

- Measure
- Decide
- Ship

***

## Revenue by segment

![Revenue climbing through Q3](chart.png)

***

## Thank you
"""

#: Layout per slide, pinned rather than selected: choosing needs a model, and
#: these tests are about what the seam does with a decision already made.
_PLAN = ["Title Slide", "Title and Content", "Title Only", "Picture with Caption", "Section Header"]


def _build(designer: Path, workspace: Path, name: str = "deck.pptx", **kwargs) -> pa.AssembleResult:
    """Assemble the fixture deck on the designer template, Seam E enabled."""
    slides = pl.segment(_SRC)
    for slide, layout in zip(slides, _PLAN, strict=True):
        slide.chosen_layout = layout
    return pa.assemble(
        slides,
        pl.extract_layouts(designer),
        designer,
        workspace / name,
        image_base_dir=workspace,
        reference_slides=True,
        **kwargs,
    )


def _all_text(deck: Path) -> list[str]:
    """Every scrap of text in the saved file, however deeply nested."""
    out: list[str] = []
    for slide in pptx.Presentation(str(deck)).slides:
        for node in slide.element.iter(qn("a:t")):
            out.append(node.text or "")
        if slide.has_notes_slide:
            out.append(slide.notes_slide.notes_text_frame.text)
    return out


def _page(designer: Path, number: int):
    """One example page of the template, by its catalog page number."""
    prs = pptx.Presentation(str(designer))
    return prs, pc.example_slides(prs)[number]


# ── reading the template ─────────────────────────────────────────────────────
class TestExamplePages:
    def test_pages_are_keyed_the_way_the_catalog_numbers_them(self, designer: Path) -> None:
        prs = pptx.Presentation(str(designer))
        assert set(pc.example_slides(prs)) == set(range(1, 9))
        # The catalog's own numbering has to agree, since that is what the
        # assembler looks pages up by.
        catalogued = {page for info in pl.extract_layouts(designer) for page in info.example_pages}
        assert catalogued <= set(pc.example_slides(prs))

    def test_the_template_pages_can_be_dropped_after_the_build(self, designer: Path) -> None:
        prs = pptx.Presentation(str(designer))
        originals = pc.template_slide_ids(prs)
        pc.clone_slide(prs, pc.example_slides(prs)[1])
        pc.drop_template_slides(prs, originals)
        assert len(prs.slides._sldIdLst) == 1  # the clone, and only the clone


# ── classification ───────────────────────────────────────────────────────────
class TestClassification:
    def test_the_title_placeholder_is_the_title(self, designer: Path) -> None:
        prs, page = _page(designer, 1)
        roles = pc.classify(page, (prs.slide_width, prs.slide_height))
        assert roles.title.text_frame.text == "DESIGNER COVER FILLER"

    def test_a_small_picture_is_furniture_and_a_big_one_is_a_slot(self, designer: Path) -> None:
        prs, cover = _page(designer, 1)
        canvas = (prs.slide_width, prs.slide_height)
        assert pc.classify(cover, canvas).pictures == []  # the logo is furniture
        _, photo_page = _page(designer, 4)
        assert len(pc.classify(photo_page, canvas).pictures) == 1

    def test_a_table_is_content_the_seam_cannot_restate(self, designer: Path) -> None:
        prs, page = _page(designer, 6)
        assert pc.classify(page, (prs.slide_width, prs.slide_height)).foreign

    def test_a_group_with_words_in_it_is_too(self, designer: Path) -> None:
        prs, page = _page(designer, 5)
        canvas = (prs.slide_width, prs.slide_height)
        assert not pc.classify(page, canvas).foreign
        _add_group_with_words(page)
        assert pc.classify(page, canvas).foreign

    def test_a_split_design_reads_down_each_panel_not_across_them(self, designer: Path) -> None:
        prs, split = _page(designer, 8)
        roles = pc.classify(split, (prs.slide_width, prs.slide_height))
        assert roles.title.text_frame.text == "DESIGNER SPLIT FILLER"
        # Left panel first, then the right panel top to bottom — not the
        # interleaving that sorting by (top, left) would give, where the
        # right-hand statement at y=1.8 would come before the lead at y=2.0.
        assert [shape.text_frame.text for shape in roles.bodies] == [
            "Designer column filler lead",
            "Designer column filler right 1",
            "Designer column filler right 2",
        ]

    def test_columns_of_one_design_are_peers_and_a_caption_is_not(self, designer: Path) -> None:
        prs, steps = _page(designer, 3)
        canvas = (prs.slide_width, prs.slide_height)
        assert len(pc.peers(pc.classify(steps, canvas).bodies)) == 3
        _, photo_page = _page(designer, 4)
        # One caption, far smaller than nothing else — still its own peer set.
        assert len(pc.peers(pc.classify(photo_page, canvas).bodies)) == 1


class TestCanCarry:
    def _roles(self, designer: Path, page: int):
        prs, slide = _page(designer, page)
        return pc.classify(slide, (prs.slide_width, prs.slide_height))

    def test_a_page_with_a_table_is_declined(self, designer: Path) -> None:
        assert not pc.can_carry(self._roles(designer, 6), pc.Content(title="Anything"))

    def test_an_image_needs_a_slot_to_land_in(self, designer: Path) -> None:
        content = pc.Content(title="A picture", image=Path("chart.png"))
        assert not pc.can_carry(self._roles(designer, 2), content)
        assert pc.can_carry(self._roles(designer, 4), content)

    def test_three_columns_need_three_bullets(self, designer: Path) -> None:
        roles = self._roles(designer, 3)
        assert not pc.can_carry(roles, pc.Content(title="Steps", bullets=["one", "two"]))
        assert pc.can_carry(roles, pc.Content(title="Steps", bullets=["one", "two", "three"]))

    def test_a_title_only_page_carries_a_title_only_slide(self, designer: Path) -> None:
        assert pc.can_carry(self._roles(designer, 5), pc.Content(title="Thank you"))


class TestDistribute:
    def test_bullets_are_split_into_balanced_columns(self) -> None:
        assert pc.distribute(list("abcde"), 3) == [["a", "b"], ["c", "d"], ["e"]]

    def test_one_frame_takes_them_all(self) -> None:
        assert pc.distribute(list("abc"), 1) == [["a", "b", "c"]]


# ── the clone itself ─────────────────────────────────────────────────────────
class TestCloneSlide:
    def test_every_shape_comes_across_once(self, designer: Path) -> None:
        prs, page = _page(designer, 1)
        before = [(s.shape_type, s.left, s.top) for s in page.shapes]
        clone = pc.clone_slide(prs, page)
        assert [(s.shape_type, s.left, s.top) for s in clone.shapes] == before

    def test_an_image_is_re_pointed_at_the_clone_s_own_relationship(self, designer: Path) -> None:
        prs, page = _page(designer, 4)
        clone = pc.clone_slide(prs, page)

        def embedded(slide) -> str:
            picture = next(s for s in slide.shapes if s.element.tag == qn("p:pic"))
            return picture.element.find(f".//{qn('a:blip')}").get(qn("r:embed"))

        source, copied = embedded(page), embedded(clone)
        # Different relationship id, same image part: a clone that kept the
        # source's rId would point at whatever that id happens to mean here.
        assert clone.part.related_part(copied) is page.part.related_part(source)

    def test_the_clone_does_not_share_the_original_s_notes(self, designer: Path) -> None:
        prs, page = _page(designer, 2)
        page.notes_slide.notes_text_frame.text = "DESIGNER private note"
        clone = pc.clone_slide(prs, page)
        assert not clone.has_notes_slide


# ── replacing the content ────────────────────────────────────────────────────
class TestCompose:
    def test_it_refuses_rather_than_half_fills(self, designer: Path) -> None:
        prs, steps = _page(designer, 3)
        assert pc.compose(prs, steps, pc.Content(title="Steps", bullets=["only one"])) is None
        # And refusing left nothing behind for the caller to clean up.
        assert len(prs.slides._sldIdLst) == 8

    def test_bullets_land_one_per_column(self, designer: Path) -> None:
        prs, steps = _page(designer, 3)
        content = pc.Content(title="Three steps", bullets=["Measure", "Decide", "Ship"])
        slide = pc.compose(prs, steps, content)
        assert [s.text_frame.text for s in slide.shapes if s.has_text_frame] == [
            "Three steps",
            "Measure",
            "Decide",
            "Ship",
        ]

    def test_bullets_inherit_the_master_s_glyph_instead_of_a_second_one(
        self, designer: Path
    ) -> None:
        prs, page = _page(designer, 2)
        content = pc.Content(title="Where we stand", bullets=["Revenue up", "Churn flat"])
        slide = pc.compose(prs, page, content)
        body = next(s for s in slide.shapes if s.text_frame.text.startswith("Revenue"))
        # Seam D has to draw its own "• " because its box has no list format;
        # a cloned paragraph already has the designer's, so a prefix here
        # would render two bullets per line.
        assert "•" not in body.text_frame.text

    def test_ornament_survives_and_filler_does_not(self, designer: Path) -> None:
        prs, page = _page(designer, 2)
        slide = pc.compose(prs, page, pc.Content(title="Where we stand", bullets=["Revenue up"]))
        texts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
        assert "01" in texts  # the chevron's number is the design
        assert not [t for t in texts if "Filler" in t]

    def test_a_picture_keeps_its_slot_and_its_place_in_the_stack(
        self, designer: Path, workspace: Path
    ) -> None:
        prs, page = _page(designer, 4)
        original = next(s for s in page.shapes if s.element.tag == qn("p:pic"))
        box = (original.left, original.top, original.width, original.height)
        depth = list(page.shapes).index(original)
        content = pc.Content(title="Revenue", image=workspace / "chart.png", alt="A chart")
        slide = pc.compose(prs, page, content)
        placed = next(s for s in slide.shapes if s.element.tag == qn("p:pic"))
        assert list(slide.shapes).index(placed) == depth
        # Contained inside the designer's slot, never stretched to fill it.
        assert placed.left >= box[0] and placed.top >= box[1]
        assert placed.width <= box[2] and placed.height <= box[3]
        assert placed._element._nvXxPr.cNvPr.get("descr") == "A chart"

    def test_an_unfilled_photo_slot_leaves_nothing_behind(
        self, designer: Path, workspace: Path
    ) -> None:
        prs, page = _page(designer, 4)
        slide = pc.compose(prs, page, pc.Content(title="No picture today"))
        assert not [s for s in slide.shapes if s.element.tag == qn("p:pic")]
        # Not just off the slide: off the relationship graph, so the designer's
        # stand-in photo does not travel inside the saved file either.
        images = [r for r in slide.part.rels.values() if r.reltype.endswith("/image")]
        assert images == []

    def test_type_under_the_legibility_floor_is_lifted_to_it(self, designer: Path) -> None:
        prs, page = _page(designer, 3)
        for box in (s for s in page.shapes if s.has_text_frame):
            for paragraph in box.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(8)
        content = pc.Content(title="Three steps", bullets=["Measure", "Decide", "Ship"])
        slide = pc.compose(prs, page, content)
        sizes = {
            run.font.size.pt
            for shape in slide.shapes
            if shape.has_text_frame
            for paragraph in shape.text_frame.paragraphs
            for run in paragraph.runs
            if run.font.size is not None
        }
        assert sizes and min(sizes) >= au.LEGIBLE_MIN_PT


# ── the seam inside the assembler ────────────────────────────────────────────
class TestAssembledDeck:
    def test_every_slide_is_carried_by_the_designer_s_own_page(
        self, designer: Path, workspace: Path
    ) -> None:
        result = _build(designer, workspace)
        assert (result.placed, result.cloned) == (5, 5)
        assert len(pptx.Presentation(str(result.pptx_path)).slides._sldIdLst) == 5

    def test_not_one_word_the_designer_wrote_ships(self, designer: Path, workspace: Path) -> None:
        result = _build(designer, workspace)
        text = "\n".join(_all_text(result.pptx_path))
        assert not [marker for marker in FILLER if marker in text]
        # The deck's own words did survive, so the assertion above is not
        # passing on an empty file.
        assert "Revenue up 18% year on year" in text

    def test_the_designer_s_furniture_does(self, designer: Path, workspace: Path) -> None:
        result = _build(designer, workspace)
        slides = list(pptx.Presentation(str(result.pptx_path)).slides)
        kinds = [s.shape_type for s in slides[0].shapes]
        assert pptx.enum.shapes.MSO_SHAPE_TYPE.AUTO_SHAPE in kinds  # the accent bar
        assert pptx.enum.shapes.MSO_SHAPE_TYPE.PICTURE in kinds  # the logo
        assert "01" in [s.text_frame.text for s in slides[1].shapes if s.has_text_frame]

    def test_the_notes_still_go_to_the_notes_pane(self, designer: Path, workspace: Path) -> None:
        result = _build(designer, workspace)
        slides = list(pptx.Presentation(str(result.pptx_path)).slides)
        assert slides[1].notes_slide.notes_text_frame.text == "Provisional until the audit closes."
        assert "audit closes" not in "\n".join(
            s.text_frame.text for s in slides[1].shapes if s.has_text_frame
        )

    def test_a_declined_page_falls_through_to_seam_d(self, designer: Path, workspace: Path) -> None:
        # Two bullets against a three-column page: Seam E must decline it, and
        # the slide must still be in the deck, built on the bare layout.
        slides = pl.segment(_SRC)
        for slide, layout in zip(slides, _PLAN, strict=True):
            slide.chosen_layout = layout
        slides[2].body = "- Measure\n- Ship\n"
        result = pa.assemble(
            slides,
            pl.extract_layouts(designer),
            designer,
            workspace / "fallback.pptx",
            image_base_dir=workspace,
            reference_slides=True,
        )
        assert result.placed == 5
        assert result.cloned == 4
        text = "\n".join(_all_text(result.pptx_path))
        assert "Measure" in text and not [marker for marker in FILLER if marker in text]

    def test_a_template_with_no_example_pages_still_builds(self, workspace: Path) -> None:
        bare = workspace / "bare.pptx"
        pptx.Presentation().save(str(bare))
        slides = pl.segment(_SRC)
        for slide, layout in zip(slides, _PLAN, strict=True):
            slide.chosen_layout = layout
        result = pa.assemble(
            slides,
            pl.extract_layouts(bare),
            bare,
            workspace / "bare-deck.pptx",
            image_base_dir=workspace,
            reference_slides=True,
        )
        # Nothing to clone, so Seam D carried all five — the flag degrades to
        # the behaviour of not passing it at all.
        assert (result.placed, result.cloned) == (5, 0)

    def test_the_deck_passes_the_audit(self, designer: Path, workspace: Path) -> None:
        result = _build(designer, workspace)
        assert au.audit(result.pptx_path) == []

    def test_building_it_twice_gives_the_same_deck(self, designer: Path, workspace: Path) -> None:
        first = _build(designer, workspace, "once.pptx")
        second = _build(designer, workspace, "twice.pptx")
        assert (first.placed, first.cloned) == (second.placed, second.cloned)
        assert _all_text(first.pptx_path) == _all_text(second.pptx_path)


# ── the flag on the command line ─────────────────────────────────────────────
class TestTheFlag:
    def test_it_is_refused_on_the_pandoc_path_rather_than_ignored(
        self, workspace: Path, caplog
    ) -> None:
        """The Pandoc writer knows nothing of example pages; say so out loud."""
        from md2star.cli import md2pptx_main

        source = workspace / "talk.md"
        source.write_text("# Talk\n\n- one\n", encoding="utf-8")
        with caplog.at_level("ERROR"):
            code = md2pptx_main([str(source), "--reference-slides"])
        assert code == 2  # InvalidInputError
        assert "--smart-layout" in caplog.text


class TestInheritedLinks:
    def test_the_designer_s_hyperlink_does_not_come_with_our_words(self, designer: Path) -> None:
        """A link lives in the run's own `rPr`, so it would outlive the text."""
        prs, page = _page(designer, 2)
        body = next(s for s in page.shapes if s.text_frame.text.startswith("Filler"))
        run = body.text_frame.paragraphs[0].runs[0]
        run.hyperlink.address = "https://designer.example/their-deck"
        slide = pc.compose(prs, page, pc.Content(title="Where we stand", bullets=["Revenue up"]))
        assert not list(slide.element.iter(qn("a:hlinkClick")))


# ── the Ralph Eyeball Loop, on this seam ─────────────────────────────────────
#: Two slides, both wanting the layout the fixture demonstrates twice.
_TWO_BULLET_SLIDES = """\
# Where we stand

- Revenue up 18% year on year
- Churn flat at 2.1%

***

## What we do next

- Re-cut the top decile
- Ship weekly
"""


#: A cover, a bullets slide on the twice-demonstrated layout, and a closing —
#: so the slide under judgement is a real content slide rather than a cover,
#: whose bullets the assembler drops by design.
_THREE = """\
# Creator Economics

***

## Where we stand

- Revenue up 18% year on year
- Churn flat at 2.1%

***

## Thank you
"""
_PLAN_TWICE = ["Title Slide", "Title and Content", "Section Header"]


def _planned(designer: Path, workspace: Path, name: str, plan: list[str], *, assemble: bool = True):
    """Segment `_THREE`, pin *plan* on it, and optionally assemble it."""
    slides = pl.segment(_THREE)
    for slide, layout in zip(slides, plan, strict=True):
        slide.chosen_layout = layout
    if not assemble:
        return slides, None
    return slides, pa.assemble(
        slides,
        pl.extract_layouts(designer),
        designer,
        workspace / name,
        image_base_dir=workspace,
        reference_slides=True,
    )


class TestEyeballLoopOnClonedSlides:
    def test_a_slide_is_judged_against_the_page_it_was_cloned_from(
        self, designer: Path, workspace: Path
    ) -> None:
        """Not the layout's first example — the one this slide actually used."""
        slides = pl.segment(_TWO_BULLET_SLIDES)
        for slide in slides:
            slide.chosen_layout = "Title and Content"
        asked: list[int] = []

        def render_template(_template, page):
            asked.append(page)
            return b"target-png"

        pa.eyeball_slides(
            slides,
            pl.extract_layouts(designer),
            designer,
            workspace / "judged.pptx",
            max_iterations=0,
            image_base_dir=workspace,
            reference_slides=True,
            chat=lambda *_a: {"matches": True},
            render_template=render_template,
            render_deck=lambda _p: {1: b"png", 2: b"png"},
        )
        # The two slides cloned the layout's two different example pages, so
        # both were offered as targets. `rep_page` alone is always the first,
        # and would have shown the judge the wrong page for the second slide.
        assert set(asked) == {2, 7}

    def test_a_page_that_is_not_carrying_a_slide_is_swapped_for_another(
        self, designer: Path, workspace: Path
    ) -> None:
        """The designer demonstrated this layout twice; try their other one."""
        _, first = _planned(designer, workspace, "first.pptx", _PLAN_TWICE)
        slides, _ = _planned(designer, workspace, "moved.pptx", _PLAN_TWICE, assemble=False)
        result = pa.eyeball_slides(
            slides,
            pl.extract_layouts(designer),
            designer,
            workspace / "moved.pptx",
            indices=[2],  # judge only the bullets slide
            max_iterations=1,
            image_base_dir=workspace,
            reference_slides=True,
            # `too_empty` has no bounded pixel-level fix, which is exactly the
            # verdict the page move exists to answer.
            chat=lambda *_a: {"matches": False, "too_empty": True, "discrepancies": "a void"},
            render_template=lambda _t, _p: b"target-png",
            render_deck=lambda _p: dict.fromkeys((1, 2, 3), b"png"),
        )
        assert first.pages[2] == 2  # the designer's first demonstration
        assert result.pages[2] == 7  # moved to their other one, same layout
        assert slides[1].chosen_layout == "Title and Content"  # not a layout swap

    def test_when_every_page_is_refused_the_slide_falls_back_to_seam_d(
        self, designer: Path, workspace: Path
    ) -> None:
        slides, _ = _planned(designer, workspace, "exhausted.pptx", _PLAN_TWICE, assemble=False)
        result = pa.eyeball_slides(
            slides,
            pl.extract_layouts(designer),
            designer,
            workspace / "exhausted.pptx",
            indices=[2],
            max_iterations=3,
            image_base_dir=workspace,
            reference_slides=True,
            chat=lambda *_a: {"matches": False, "too_empty": True, "discrepancies": "a void"},
            render_template=lambda _t, _p: b"target-png",
            render_deck=lambda _p: dict.fromkeys((1, 2, 3), b"png"),
            allow_reselect=False,
        )
        # Both demonstrations judged and refused: the slide is still in the
        # deck, built on the bare layout, which is the safe generic this loop
        # has always fallen back to. The slides nobody complained about keep
        # their cloned pages.
        assert result.placed == 3
        assert 2 not in result.pages
        text = "\n".join(_all_text(result.pptx_path))
        assert "Revenue up 18% year on year" in text
        assert not [marker for marker in FILLER if marker in text]

    def test_a_cloned_slide_gets_the_sharper_question(
        self, designer: Path, workspace: Path
    ) -> None:
        """Same page, different content — so ask what the replacement broke."""
        slides, _ = _planned(designer, workspace, "asked.pptx", _PLAN_TWICE, assemble=False)
        prompts: list[str] = []

        def record(prompt, _images, _schema):
            prompts.append(prompt)
            return {"matches": True}

        pa.eyeball_slides(
            slides,
            pl.extract_layouts(designer),
            designer,
            workspace / "asked.pptx",
            max_iterations=0,
            image_base_dir=workspace,
            reference_slides=True,
            chat=record,
            render_template=lambda _t, _p: b"target-png",
            render_deck=lambda _p: dict.fromkeys((1, 2, 3), b"png"),
        )
        assert prompts and all("rebuilt with different" in p for p in prompts)
        # And the family-resemblance question is what a non-cloned deck gets.
        plain = pl.segment(_THREE)
        for slide, layout in zip(plain, _PLAN_TWICE, strict=True):
            slide.chosen_layout = layout
        prompts.clear()
        pa.eyeball_slides(
            plain,
            pl.extract_layouts(designer),
            designer,
            workspace / "plain.pptx",
            max_iterations=0,
            image_base_dir=workspace,
            chat=record,
            render_template=lambda _t, _p: b"target-png",
            render_deck=lambda _p: dict.fromkeys((1, 2, 3), b"png"),
        )
        assert prompts and not any("rebuilt with different" in p for p in prompts)
