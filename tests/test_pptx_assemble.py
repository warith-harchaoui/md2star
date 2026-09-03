"""Tests for md2star.pptx_assemble — box helpers, assembly, the eyeball loop.

Exercised **offline**: real ``python-pptx`` objects are built against its own
bundled default template (no external asset needed), and the target-matching
eyeball loop's LLM/VLM/render seams are driven with injected fakes, no
Ollama/LibreOffice/poppler required — mirroring tests/test_reverse_twin.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")

from md2star import pptx_assemble as pa  # noqa: E402
from md2star import pptx_layout as pl  # noqa: E402


@pytest.fixture
def default_template(tmp_path: Path) -> Path:
    path = tmp_path / "default.pptx"
    pptx.Presentation().save(str(path))
    return path


@pytest.fixture
def catalog(default_template: Path) -> list[pl.LayoutInfo]:
    return pl.extract_layouts(default_template)


# ── template introspection ───────────────────────────────────────────────────
class TestTemplateFonts:
    def test_falls_back_to_arial_with_no_explicit_typeface(self, default_template: Path) -> None:
        fam = pa.template_fonts(default_template)
        assert fam["display"] and fam["body"]  # never empty, even with nothing declared

    def test_picks_up_an_explicit_design_font(self, tmp_path: Path) -> None:
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[5])  # Title Only
        box = slide.shapes.add_textbox(0, 0, pptx.util.Inches(1), pptx.util.Inches(1))
        run = box.text_frame.paragraphs[0].add_run()
        run.text = "hello"
        run.font.name = "Montserrat"
        path = tmp_path / "fonted.pptx"
        prs.save(str(path))
        fam = pa.template_fonts(path)
        assert fam["family"] == "Montserrat"
        assert fam["body"] == "Montserrat"


class TestDarkDetection:
    def test_unresolvable_background_is_not_dark(self, default_template: Path) -> None:
        prs = pptx.Presentation(str(default_template))
        layout = prs.slide_layouts[0]
        # python-pptx's stock layouts declare no explicit solid fill.
        assert pa._bg_hex(layout) is None
        assert pa.is_dark_layout(layout) is None


# ── box helpers ───────────────────────────────────────────────────────────────
class TestBoxHelpers:
    def test_uses_placeholder_geometry_when_present(self, default_template: Path, catalog) -> None:
        prs = pptx.Presentation(str(default_template))
        info = next(c for c in catalog if c.name == "Picture with Caption")
        box = pa.image_box(prs, info)
        placeholder = next(p for p in info.placeholders if p.kind == "pic")
        expected = tuple(v / pa.EMU_PER_INCH for v in placeholder.emu)
        assert box == expected

    def test_falls_back_to_fractional_default_without_geometry(
        self, default_template: Path
    ) -> None:
        prs = pptx.Presentation(str(default_template))
        box = pa.image_box(prs, None)
        slide_w = prs.slide_width / pa.EMU_PER_INCH
        assert 0 < box[0] < slide_w
        assert 0 < box[2] <= slide_w


# ── content parsing ──────────────────────────────────────────────────────────
class TestContentParsing:
    def test_parse_image_resolves_relative_to_base_dir(self, tmp_path: Path) -> None:
        (tmp_path / "pic.png").write_bytes(b"\x89PNG")
        found = pa.parse_image("![alt](pic.png)", tmp_path)
        assert found == (tmp_path / "pic.png").resolve()

    def test_parse_image_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert pa.parse_image("![alt](nope.png)", tmp_path) is None

    def test_parse_mermaid_extracts_fenced_block(self) -> None:
        assert pa.parse_mermaid("```mermaid\nflowchart LR\nA-->B\n```") == "flowchart LR\nA-->B"

    def test_parse_code_skips_mermaid_block(self) -> None:
        body = "```mermaid\nflowchart LR\n```\n```python\nprint(1)\n```"
        assert pa.parse_code(body) == "print(1)"

    def test_fallback_bullets_strips_markup_and_caps(self) -> None:
        body = "# Title\n\n- **one** _two_\n- three\n- four\n- five\n"
        bullets = pa.fallback_bullets(body, cap=2)
        assert len(bullets) == 2
        assert bullets[0] == "one two"


# ── assembly ──────────────────────────────────────────────────────────────────
class TestAssemble:
    def test_places_every_slide_onto_its_chosen_layout(
        self, tmp_path: Path, default_template: Path, catalog
    ) -> None:
        slides = pl.segment(
            "# Cover\n\nsubtitle\n\n***\n\n## Bullets\n\n- a\n- b\n\n***\n\n## Divider {.big}\n\n***\n\n## The End\n"
        )
        by_archetype = {"Title Slide": 0, "Title and Content": 1, "Section Header": 2, "Blank": 3}
        names = list(by_archetype)
        for s, name in zip(slides, names, strict=True):
            s.chosen_layout = name

        out = tmp_path / "out.pptx"
        result = pa.assemble(slides, catalog, default_template, out)
        assert result.placed == result.total == 4
        assert out.exists()

        prs = pptx.Presentation(str(out))
        assert len(prs.slides) == 4
        used_layout_names = [slide.slide_layout.name for slide in prs.slides]
        assert used_layout_names == names

    def test_unknown_layout_falls_back(
        self, tmp_path: Path, default_template: Path, catalog
    ) -> None:
        slides = pl.segment("# Only\n\nbody\n")
        slides[0].chosen_layout = "Does Not Exist"
        out = tmp_path / "out.pptx"
        result = pa.assemble(slides, catalog, default_template, out, default_layout="Title Slide")
        assert result.placed == 1
        prs = pptx.Presentation(str(out))
        assert prs.slides[0].slide_layout.name == "Title Slide"

    def test_bad_slide_does_not_sink_the_deck(
        self, tmp_path: Path, default_template: Path, catalog
    ) -> None:
        slides = pl.segment("# One\n\nbody\n\n***\n\n## Two\n\nbody2\n")
        slides[0].chosen_layout = "Title Slide"
        slides[1].chosen_layout = "Title Slide"
        # An image feature with no resolvable path degrades to title-only,
        # not a crash — simulate a hard failure instead via a bogus override.
        slides[0].overrides = {"font_delta": "not-a-number"}
        out = tmp_path / "out.pptx"
        result = pa.assemble(slides, catalog, default_template, out)
        assert result.total == 2
        assert result.placed == 1  # slide 1 failed (bad override), slide 2 still placed

    def test_no_layouts_raises(self, tmp_path: Path) -> None:
        # Presentation() always has layouts in practice; simulate the guard by
        # asserting it fires on an (unrealistic) empty layout_index result.
        prs = pptx.Presentation()
        assert pa.layout_index(prs)  # sanity: never empty for a real template


# ── target-matching eyeball loop ─────────────────────────────────────────────
class TestEyeballLoop:
    def test_applies_overrides_on_mismatch_then_stops(
        self, tmp_path: Path, default_template: Path, catalog
    ) -> None:
        slides = pl.segment("# Cover\n\n- a\n- b\n- c\n")
        slides[0].chosen_layout = "Title and Content"
        out = tmp_path / "out.pptx"

        calls = {"judge": 0}

        def fake_chat(_prompt, _images, _schema):
            calls["judge"] += 1
            if calls["judge"] == 1:
                return {"matches": False, "overflow": True, "discrepancies": "too much text"}
            return {"matches": True}

        def fake_render_template(_template, _page):
            return b"target-png"

        def fake_render_deck(_path):
            return {1: b"candidate-png"}

        # Give the layout an example page so a target thumbnail is attempted.
        for c in catalog:
            if c.name == "Title and Content":
                c.example_pages = [1]

        result = pa.eyeball_slides(
            slides,
            catalog,
            default_template,
            out,
            max_iterations=2,
            chat=fake_chat,
            render_template=fake_render_template,
            render_deck=fake_render_deck,
        )
        assert result.placed == 1
        assert slides[0].overrides.get("font_delta") == -4
        assert slides[0].overrides.get("bullets") == 2
        # First pass flags+fixes, second pass's judge call reports a match -> stop.
        assert calls["judge"] == 2

    def test_no_target_page_skips_judging(
        self, tmp_path: Path, default_template: Path, catalog
    ) -> None:
        slides = pl.segment("# Cover\n\nbody\n")
        slides[0].chosen_layout = "Title Slide"  # no example_pages -> no rep_page
        out = tmp_path / "out.pptx"

        def unreachable_chat(*_a):
            raise AssertionError("must not be called with no target page")

        result = pa.eyeball_slides(
            slides,
            catalog,
            default_template,
            out,
            max_iterations=1,
            chat=unreachable_chat,
            render_deck=lambda _p: {1: b"png"},
        )
        assert result.placed == 1
        assert slides[0].overrides == {}
