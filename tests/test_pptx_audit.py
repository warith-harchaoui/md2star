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


def _one_pixel_png(path: Path) -> None:
    """Write the smallest valid PNG, so add_picture has real bytes to read."""
    from PIL import Image

    Image.new("RGB", (8, 8), "white").save(path)
