"""Tests for md2star.pptx_audit — the model-free deck audit.

Exercised **offline** against real ``python-pptx`` objects: every check is
arithmetic on a saved ``.pptx``, so a deliberately broken deck is built here
shape by shape and the findings are asserted exactly. No model, no LibreOffice,
no network — that independence is the point of the module.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")

from pptx.util import Inches, Pt  # noqa: E402

from md2star import pptx_assemble as pa  # noqa: E402
from md2star import pptx_audit as au  # noqa: E402
from md2star import pptx_layout as pl  # noqa: E402


def _blank() -> "pptx.presentation.Presentation":
    """A one-slide deck on the stock blank layout (no placeholders at all)."""
    prs = pptx.Presentation()
    prs.slides.add_slide(prs.slide_layouts[6])
    return prs


def _text(slide, box: tuple[float, float, float, float], text: str, pt: float):
    """Add a sized text box, in inches, with an explicit run size."""
    shape = slide.shapes.add_textbox(*(Inches(v) for v in box))
    shape.text_frame.text = text
    shape.text_frame.paragraphs[0].runs[0].font.size = Pt(pt)
    return shape


def _saved(prs, tmp_path: Path, name: str = "deck.pptx") -> Path:
    out = tmp_path / name
    prs.save(str(out))
    return out


def _kinds(findings: list[au.Finding]) -> list[str]:
    return [f.kind for f in findings]


# ── a clean deck ─────────────────────────────────────────────────────────────
class TestCleanDeck:
    def test_an_assembled_deck_has_nothing_to_report(self, tmp_path: Path) -> None:
        """The assembler's own output is the audit's reference "clean"."""
        template = _saved(pptx.Presentation(), tmp_path, "template.pptx")
        catalog = pl.extract_layouts(template)
        slides = pl.segment("# Cover\n\n***\n\n## Points\n\n- a\n- b\n\n***\n\n## End\n")
        for slide in slides:
            slide.chosen_layout = "Picture with Caption"
        out = tmp_path / "out.pptx"
        pa.assemble(slides, catalog, template, out)
        assert au.audit(out) == []

    def test_summary_says_clean(self) -> None:
        assert au.summarise([], slides=12) == "layout audit: clean (12 slides)"


# ── off-slide ────────────────────────────────────────────────────────────────
class TestOffSlide:
    def test_a_shape_past_the_right_edge_is_flagged(self, tmp_path: Path) -> None:
        prs = _blank()
        # The stock canvas is 10 x 7.5in; this starts at 9in and is 3in wide.
        _text(prs.slides[0], (9, 1, 3, 1), "runs off", 18)
        findings = au.audit(_saved(prs, tmp_path))
        assert _kinds(findings) == ["off-slide"]
        assert "right edge" in findings[0].detail

    def test_a_negative_offset_is_flagged(self, tmp_path: Path) -> None:
        prs = _blank()
        _text(prs.slides[0], (-2, 1, 3, 1), "off the left", 18)
        assert "left edge" in au.audit(_saved(prs, tmp_path))[0].detail

    def test_a_hairline_bleed_is_tolerated(self, tmp_path: Path) -> None:
        """Designer templates bleed a band a hair past the edge on purpose."""
        prs = _blank()
        width = prs.slide_width / 914400
        _text(prs.slides[0], (width - 2 + 0.02, 1, 2, 1), "just touching", 18)
        assert au.audit(_saved(prs, tmp_path)) == []


# ── overlap ──────────────────────────────────────────────────────────────────
class TestOverlap:
    def test_two_stacked_text_boxes_are_flagged(self, tmp_path: Path) -> None:
        prs = _blank()
        _text(prs.slides[0], (1, 1, 4, 1), "first", 18)
        _text(prs.slides[0], (1.2, 1.1, 4, 1), "second", 18)
        findings = au.audit(_saved(prs, tmp_path))
        assert _kinds(findings) == ["overlap"]
        assert "share" in findings[0].detail

    def test_a_touching_corner_is_not_an_overlap(self, tmp_path: Path) -> None:
        prs = _blank()
        _text(prs.slides[0], (1, 1, 4, 1), "first", 18)
        _text(prs.slides[0], (4.9, 1.9, 4, 1), "second", 18)
        assert au.audit(_saved(prs, tmp_path)) == []

    def test_text_over_a_picture_is_a_composition_not_a_bug(self, tmp_path: Path) -> None:
        """Half the point of a photo-hero layout is a title on the image."""
        prs = _blank()
        slide = prs.slides[0]
        png = tmp_path / "px.png"
        _one_pixel_png(png)
        slide.shapes.add_picture(str(png), Inches(1), Inches(1), Inches(6), Inches(4))
        _text(slide, (1.5, 2, 4, 1), "title on the photo", 28)
        assert au.audit(_saved(prs, tmp_path)) == []


# ── type size ────────────────────────────────────────────────────────────────
class TestIllegibleType:
    def test_a_run_under_the_floor_is_flagged(self, tmp_path: Path) -> None:
        prs = _blank()
        _text(prs.slides[0], (1, 1, 6, 1), "tiny", 8)
        findings = au.audit(_saved(prs, tmp_path))
        assert _kinds(findings) == ["illegible-type"]
        assert "8pt" in findings[0].detail

    def test_the_floor_itself_passes(self, tmp_path: Path) -> None:
        prs = _blank()
        _text(prs.slides[0], (1, 1, 6, 1), "small but readable", au.LEGIBLE_MIN_PT)
        assert au.audit(_saved(prs, tmp_path)) == []

    def test_inherited_sizing_is_not_guessed(self, tmp_path: Path) -> None:
        """No explicit size means the master decides; this module declines to."""
        prs = _blank()
        shape = prs.slides[0].shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(1))
        shape.text_frame.text = "whatever the master says"
        assert au.audit(_saved(prs, tmp_path)) == []


# ── overrun ──────────────────────────────────────────────────────────────────
class TestOverrun:
    def test_text_too_big_for_its_box_reports_the_size_that_fits(self, tmp_path: Path) -> None:
        prs = _blank()
        _text(
            prs.slides[0],
            (0.5, 1, 2, 0.5),
            "a long sentence that cannot possibly fit a two by half inch box at this size",
            24,
        )
        findings = au.audit(_saved(prs, tmp_path))
        assert _kinds(findings) == ["overrun"]
        assert "fits at ~" in findings[0].detail

    def test_a_comfortable_box_is_not_flagged(self, tmp_path: Path) -> None:
        prs = _blank()
        _text(prs.slides[0], (0.5, 1, 8, 2), "a short line", 24)
        assert au.audit(_saved(prs, tmp_path)) == []

    def test_mixed_sizes_are_measured_paragraph_by_paragraph(self, tmp_path: Path) -> None:
        """A 26pt heading over 16pt bullets costs what each actually costs."""
        prs = _blank()
        shape = prs.slides[0].shapes.add_textbox(Inches(0.5), Inches(1), Inches(8), Inches(3))
        frame = shape.text_frame
        frame.text = "Heading"
        frame.paragraphs[0].runs[0].font.size = Pt(26)
        for line in ("first bullet", "second bullet"):
            para = frame.add_paragraph()
            para.text = line
            para.runs[0].font.size = Pt(16)
        assert au.audit(_saved(prs, tmp_path)) == []


# ── ghost placeholders ───────────────────────────────────────────────────────
class TestGhostPlaceholder:
    def test_an_unfilled_placeholder_is_flagged(self, tmp_path: Path) -> None:
        """The invariant drop_empty_placeholders() maintains, checked on disk."""
        prs = pptx.Presentation()
        prs.slides.add_slide(prs.slide_layouts[8])  # title + picture + body
        findings = au.audit(_saved(prs, tmp_path))
        assert set(_kinds(findings)) == {"ghost-placeholder"}
        assert len(findings) == 3


# ── reporting ────────────────────────────────────────────────────────────────
class TestReporting:
    def test_findings_are_sorted_by_slide_then_severity(self, tmp_path: Path) -> None:
        prs = _blank()
        prs.slides.add_slide(prs.slide_layouts[6])
        _text(prs.slides[0], (1, 1, 6, 1), "tiny", 8)
        _text(prs.slides[1], (9, 1, 3, 1), "off the edge", 18)
        findings = au.audit(_saved(prs, tmp_path))
        assert [(f.slide, f.kind) for f in findings] == [
            (1, "illegible-type"),
            (2, "off-slide"),
        ]

    def test_the_summary_counts_slides_and_kinds(self) -> None:
        findings = [
            au.Finding(1, "overlap", "x"),
            au.Finding(1, "overrun", "y"),
            au.Finding(4, "overlap", "z"),
        ]
        line = au.summarise(findings, slides=10)
        assert line.startswith("layout audit: 3 findings on 2 slides")
        assert "2 overlap" in line and "1 overrun" in line

    def test_a_finding_prints_as_one_actionable_line(self) -> None:
        text = str(au.Finding(3, "overlap", "they share 40%", shape="Title 1"))
        assert text == "slide 3: overlap [Title 1] — they share 40%"


# ── the `md2star audit` command ──────────────────────────────────────────────
# The audit is a tool in its own right: it reads any .pptx, including ones
# PowerPoint made, so the exit status has to be usable from a CI job.
class TestCommandLine:
    @pytest.fixture
    def broken(self, tmp_path: Path) -> Path:
        prs = _blank()
        _text(prs.slides[0], (1, 1, 4, 1), "first", 18)
        _text(prs.slides[0], (1.2, 1.1, 4, 1), "second", 18)
        return _saved(prs, tmp_path, "broken.pptx")

    @pytest.fixture
    def dense(self, tmp_path: Path) -> Path:
        """A deck whose only sin is too much text — an observation, not a defect."""
        prs = _blank()
        _text(prs.slides[0], (0.5, 1, 2, 0.5), "a sentence far too long for this little box", 24)
        return _saved(prs, tmp_path, "dense.pptx")

    def test_a_clean_deck_exits_zero(self, tmp_path: Path, capsys) -> None:
        clean = _saved(_blank(), tmp_path, "clean.pptx")
        assert au.run(str(clean)) == 0
        assert "clean" in capsys.readouterr().out

    def test_a_defect_exits_one(self, broken: Path, capsys) -> None:
        assert au.run(str(broken)) == 1
        assert "overlap" in capsys.readouterr().out

    def test_an_overrun_alone_is_not_a_failure(self, dense: Path) -> None:
        """PowerPoint auto-shrinks the text, so a dense deck is a choice."""
        assert au.run(str(dense)) == 0

    def test_strict_makes_an_overrun_a_failure(self, dense: Path) -> None:
        assert au.run(str(dense), strict=True) == 1

    def test_json_output_is_parseable(self, broken: Path, capsys) -> None:
        import json

        assert au.run(str(broken), as_json=True) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["kind"] == "overlap"
        assert set(payload[0]) == {"slide", "kind", "detail", "shape"}

    def test_an_overrun_carries_its_two_numbers_in_the_json(self, dense: Path, capsys) -> None:
        """The size it declares and the size that would fit, as numbers."""
        import json

        au.run(str(dense), as_json=True)
        payload = json.loads(capsys.readouterr().out)
        overrun = next(row for row in payload if row["kind"] == "overrun")
        assert overrun["fits_pt"] < overrun["measured_pt"]
        # And the numbers say the same thing the sentence does.
        assert f"{overrun['fits_pt']:.0f}pt" in overrun["detail"]

    def test_a_missing_file_is_a_usage_error(self, tmp_path: Path, capsys) -> None:
        assert au.run(str(tmp_path / "nope.pptx")) == 2
        assert "no such file" in capsys.readouterr().err

    def test_a_file_that_is_not_a_deck_is_a_usage_error(self, tmp_path: Path, capsys) -> None:
        notes = tmp_path / "notes.md"
        notes.write_text("# not a deck")
        assert au.run(str(notes)) == 2
        assert "cannot read" in capsys.readouterr().err


def _one_pixel_png(path: Path) -> None:
    """Write the smallest valid PNG, so add_picture has real bytes to read."""
    from PIL import Image

    Image.new("RGB", (8, 8), "white").save(path)


class TestContrast:
    """The WCAG ratio, measured, with the backdrop resolved like a renderer."""

    def _deck(self, tmp_path, text_rgb, panel_rgb=None, pt=28, on_layout=False):
        pptx = pytest.importorskip("pptx")
        from pptx.dml.color import RGBColor
        from pptx.enum.shapes import MSO_SHAPE
        from pptx.util import Inches, Pt

        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
        if panel_rgb is not None:
            panel = slide.shapes.add_shape(
                MSO_SHAPE.RECTANGLE, Inches(0.0), Inches(0.0), Inches(9.0), Inches(6.0)
            )
            panel.fill.solid()
            panel.fill.fore_color.rgb = RGBColor(*panel_rgb)
            panel.line.fill.background()
            if on_layout:
                # python-pptx can only *build* a shape on a slide, and the
                # case worth testing is a panel that lives on the layout — so
                # the element is moved there, which is where a real designer
                # template keeps it.
                element = panel.element
                element.getparent().remove(element)
                slide.slide_layout.shapes._spTree.append(element)
        box = slide.shapes.add_textbox(Inches(1.0), Inches(1.0), Inches(5.0), Inches(1.5))
        run = box.text_frame.paragraphs[0].add_run()
        run.text = "Readable?"
        run.font.size = Pt(pt)
        run.font.color.rgb = RGBColor(*text_rgb)
        out = tmp_path / "contrast.pptx"
        prs.save(str(out))
        return out

    def _kinds(self, deck):
        return [f.kind for f in au.audit(deck)]

    def test_pale_grey_on_near_white_is_flagged(self, tmp_path: Path) -> None:
        deck = self._deck(tmp_path, (0xC8, 0xC8, 0xC8), (0xF2, 0xF2, 0xF2))
        finding = next(f for f in au.audit(deck) if f.kind == "low-contrast")
        assert "1.5:1" in finding.detail and "3:1" in finding.detail

    def test_black_on_white_is_not(self, tmp_path: Path) -> None:
        assert "low-contrast" not in self._kinds(self._deck(tmp_path, (0, 0, 0)))

    def test_the_panel_a_heading_sits_on_counts_even_from_the_layout(self, tmp_path: Path) -> None:
        """The case that makes this check worth writing carefully."""
        # Black type on a layout's own dark panel: unreadable, and invisible to
        # anything that only reads the slide's shapes.
        deck = self._deck(tmp_path, (0, 0, 0), (0x14, 0x14, 0x16), on_layout=True)
        assert "low-contrast" in self._kinds(deck)
        # The same panel with white type on it reads perfectly.
        clean = self._deck(tmp_path, (0xFF, 0xFF, 0xFF), (0x14, 0x14, 0x16), on_layout=True)
        assert "low-contrast" not in self._kinds(clean)

    def test_small_type_is_held_to_the_stricter_floor(self, tmp_path: Path) -> None:
        # 3.6:1 passes the large-type floor and fails the body-copy one, so the
        # same two colours are a finding at 12 pt and not at 28 pt.
        pale, panel = (0x94, 0x94, 0x94), (0xFF, 0xFF, 0xFF)
        assert "low-contrast" not in self._kinds(self._deck(tmp_path, pale, panel, pt=28))
        assert "low-contrast" in self._kinds(self._deck(tmp_path, pale, panel, pt=12))

    def test_a_backdrop_nobody_can_read_is_left_unjudged(self, tmp_path: Path) -> None:
        """A photograph behind the text: unknowable, so not a finding."""
        pytest.importorskip("PIL")
        from PIL import Image
        from pptx.dml.color import RGBColor
        from pptx.util import Inches, Pt

        photo = tmp_path / "photo.png"
        Image.new("RGB", (800, 600), (250, 250, 250)).save(photo)
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        slide.shapes.add_picture(str(photo), Inches(0), Inches(0), Inches(9), Inches(6))
        box = slide.shapes.add_textbox(Inches(1.0), Inches(1.0), Inches(5.0), Inches(1.5))
        run = box.text_frame.paragraphs[0].add_run()
        run.text = "Over a photograph"
        run.font.size = Pt(28)
        run.font.color.rgb = RGBColor(0xFA, 0xFA, 0xFA)  # white on a white photo
        deck = tmp_path / "photo-deck.pptx"
        prs.save(str(deck))
        assert "low-contrast" not in self._kinds(deck)

    def test_the_ratio_is_the_wcag_one(self) -> None:
        from pptx.dml.color import RGBColor

        black, white = RGBColor(0, 0, 0), RGBColor(0xFF, 0xFF, 0xFF)
        assert au._contrast_ratio(black, white) == pytest.approx(21.0, abs=0.01)
        assert au._contrast_ratio(white, white) == pytest.approx(1.0, abs=0.001)
