"""Tests for md2star.pptx_layout — catalog extraction, segmentation, selection.

Exercised **offline**: the deterministic catalog/segment stages need only
``python-pptx`` (its own bundled default template is a real, always-available
PPTX with no external asset), and the LLM/VLM stages are driven with injected
fakes (mirroring tests/test_reverse_twin.py), no Ollama required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")

from md2star import pptx_layout as pl  # noqa: E402


@pytest.fixture
def default_template(tmp_path: Path) -> Path:
    """python-pptx's own bundled default template: 11 real layouts, no example slides."""
    path = tmp_path / "default.pptx"
    pptx.Presentation().save(str(path))
    return path


# ── deterministic catalog extraction ─────────────────────────────────────────
class TestExtractLayouts:
    def test_extracts_every_layout_even_with_no_example_slides(
        self, default_template: Path
    ) -> None:
        layouts = pl.extract_layouts(default_template)
        names = {layout.name for layout in layouts}
        assert "Title Slide" in names
        assert "Picture with Caption" in names
        # No slide in a fresh Presentation() uses any layout yet.
        assert all(layout.example_pages == [] for layout in layouts)

    def test_picture_placeholder_has_geometry(self, default_template: Path) -> None:
        layouts = {layout.name: layout for layout in pl.extract_layouts(default_template)}
        pic = layouts["Picture with Caption"]
        assert pic.has_kind("pic")
        placeholder = next(p for p in pic.placeholders if p.kind == "pic")
        assert placeholder.emu is not None
        assert all(v > 0 for v in placeholder.emu)

    def test_no_name_collapses_into_reference_hints(self, default_template: Path) -> None:
        # None of python-pptx's stock layouts look like brand-reference pages.
        layouts = pl.extract_layouts(default_template)
        assert all(layout.is_content_layout for layout in layouts)

    def test_rep_page_is_none_without_examples(self, default_template: Path) -> None:
        layouts = pl.extract_layouts(default_template)
        assert all(layout.rep_page is None for layout in layouts)


# ── deck segmentation ────────────────────────────────────────────────────────
class TestSegment:
    def test_splits_on_horizontal_rules(self) -> None:
        md = "# Title\n\nIntro\n\n***\n\n## Second\n\n- a\n- b\n"
        slides = pl.segment(md)
        assert len(slides) == 2
        assert slides[0].title == "Title"
        assert slides[1].title == "Second"
        assert "bullets" in slides[1].features

    def test_falls_back_to_headings_without_hr(self) -> None:
        md = "# One\n\nbody\n\n## Two\n\nmore body\n"
        slides = pl.segment(md)
        assert [s.title for s in slides] == ["One", "Two"]

    def test_strips_html_comments_before_titling(self) -> None:
        md = "<!-- note -->\n# Real Title\n\nbody\n"
        slides = pl.segment(md)
        assert slides[0].title == "Real Title"

    def test_detects_features(self) -> None:
        md = (
            "# T\n\n```mermaid\nflowchart LR\nA-->B\n```\n\n"
            "1. step\n\n> a quote\n\n| a | b |\n|---|---|\n"
        )
        slides = pl.segment(md)
        f = set(slides[0].features)
        assert {"mermaid", "ordered-list", "quote", "table"} <= f

    def test_empty_chunks_are_dropped(self) -> None:
        md = "# T\n\nbody\n\n***\n\n   \n\n***\n\n## U\n\nbody2\n"
        slides = pl.segment(md)
        assert [s.title for s in slides] == ["T", "U"]


# ── catalog build (deterministic-only, no vision) ────────────────────────────
class TestBuildCatalog:
    def test_no_vision_uses_deterministic_extraction(
        self, tmp_path: Path, default_template: Path
    ) -> None:
        cache = tmp_path / "catalog.json"
        catalog = pl.build_catalog(default_template, use_vision=False, cache_path=cache)
        assert {c.name for c in catalog} == {c.name for c in pl.extract_layouts(default_template)}
        assert cache.exists()

    def test_cache_round_trips(self, tmp_path: Path, default_template: Path) -> None:
        cache = tmp_path / "catalog.json"
        first = pl.build_catalog(default_template, use_vision=False, cache_path=cache)
        second = pl.build_catalog(default_template, use_vision=False, cache_path=cache)
        assert [c.name for c in first] == [c.name for c in second]

    def test_vision_captions_when_examples_and_transport_available(self, tmp_path: Path) -> None:
        # Build a template with ONE slide (so the "Title Slide" layout has a
        # renderable example) and a fake render+chat pair.
        prs = pptx.Presentation()
        prs.slides.add_slide(prs.slide_layouts[0])
        template = tmp_path / "one_slide.pptx"
        prs.save(str(template))

        def fake_render(_template: Path, page: int) -> bytes | None:
            return b"png-bytes" if page == 1 else None

        def fake_chat(_prompt: str, images, _schema):
            assert images  # the caption stage must pass the rendered thumbnail(s)
            return {"archetype": "cover", "is_content_layout": True, "one_line": "a cover slide"}

        cache = tmp_path / "catalog.json"
        catalog = pl.build_catalog(template, chat=fake_chat, render=fake_render, cache_path=cache)
        title_slide = next(c for c in catalog if c.name == "Title Slide")
        assert title_slide.archetype == "cover"
        assert title_slide.caption == "a cover slide"


# ── LLM text-based selection ─────────────────────────────────────────────────
class TestSelectLayouts:
    def test_assigns_catalog_name_from_fake_llm(self) -> None:
        slides = pl.segment("# Cover\n\nsubtitle\n\n***\n\n## Bullets\n\n- a\n- b\n")
        catalog = [
            pl.LayoutInfo(name="Cover Layout", archetype="cover", is_content_layout=True),
            pl.LayoutInfo(
                name="Bulleted Layout", archetype="bulleted-content", is_content_layout=True
            ),
        ]

        def fake_chat(_prompt: str, _images, _schema):
            return {
                "choices": [
                    {"index": 1, "layout_name": "Cover Layout", "confidence": 0.9, "why": "opener"},
                    {
                        "index": 2,
                        "layout_name": "Bulleted Layout",
                        "confidence": 0.8,
                        "why": "list",
                    },
                ]
            }

        pl.select_layouts(slides, catalog, chat=fake_chat)
        assert slides[0].chosen_layout == "Cover Layout"
        assert slides[1].chosen_layout == "Bulleted Layout"
        assert slides[1].chosen_why == "list"

    def test_falls_back_on_unparseable_reply(self) -> None:
        slides = pl.segment("# Cover\n\nbody\n")
        catalog = [
            pl.LayoutInfo(
                name="Bulleted Layout", archetype="bulleted-content", is_content_layout=True
            )
        ]
        pl.select_layouts(slides, catalog, chat=lambda *_: "not json")
        assert slides[0].chosen_layout == "Bulleted Layout"  # never left unassigned

    def test_drops_reference_layouts_from_the_offer(self) -> None:
        slides = pl.segment("# T\n\nbody\n")
        catalog = [
            pl.LayoutInfo(
                name="Brand Colours", archetype="reference-non-content", is_content_layout=False
            ),
            pl.LayoutInfo(
                name="Bulleted Layout", archetype="bulleted-content", is_content_layout=True
            ),
        ]

        def fake_chat(prompt: str, _images, _schema):
            assert "Brand Colours" not in prompt  # never offered to the model
            return json.dumps({"choices": []})

        pl.select_layouts(slides, catalog, chat=fake_chat)
        assert slides[0].chosen_layout == "Bulleted Layout"

    def test_no_content_layouts_is_a_noop(self) -> None:
        slides = pl.segment("# T\n\nbody\n")
        catalog = [pl.LayoutInfo(name="Ref", is_content_layout=False)]
        pl.select_layouts(slides, catalog, chat=lambda *_: "unreachable")
        assert slides[0].chosen_layout is None


# ── VLM visual tie-break ─────────────────────────────────────────────────────
class TestVisualConfirm:
    def test_overrides_on_disagreement(self, tmp_path: Path) -> None:
        template = tmp_path / "t.pptx"
        template.write_bytes(b"")  # never opened; render is faked
        slides = pl.segment("# T\n\n- a\n- b\n")
        slides[0].chosen_layout = "Layout A"
        catalog = [
            pl.LayoutInfo(
                name="Layout A",
                archetype="bulleted-content",
                is_content_layout=True,
                example_pages=[1],
            ),
            pl.LayoutInfo(
                name="Layout B", archetype="photo-hero", is_content_layout=True, example_pages=[2]
            ),
        ]

        def fake_render(_template: Path, page: int) -> bytes | None:
            return f"png-{page}".encode()

        def fake_chat(_prompt: str, images, _schema):
            assert len(images) == 2
            return {"best": "Layout B", "why": "fits better"}

        pl.visual_confirm(slides, catalog, chat=fake_chat, render=fake_render, template=template)
        assert slides[0].chosen_layout == "Layout B"
        assert slides[0].chosen_why == "fits better"

    def test_keeps_pick_when_render_unavailable(self, tmp_path: Path) -> None:
        template = tmp_path / "t.pptx"
        slides = pl.segment("# T\n\n- a\n")
        slides[0].chosen_layout = "Layout A"
        catalog = [
            pl.LayoutInfo(
                name="Layout A",
                archetype="bulleted-content",
                is_content_layout=True,
                example_pages=[1],
            ),
            pl.LayoutInfo(
                name="Layout B", archetype="photo-hero", is_content_layout=True, example_pages=[2]
            ),
        ]
        pl.visual_confirm(
            slides,
            catalog,
            chat=lambda *_: {"best": "Layout B"},
            render=lambda *_: None,
            template=template,
        )
        assert slides[0].chosen_layout == "Layout A"  # unchanged: nothing to compare

    def test_noop_without_template(self) -> None:
        slides = pl.segment("# T\n\n- a\n")
        slides[0].chosen_layout = "Layout A"
        pl.visual_confirm(slides, [], template=None)
        assert slides[0].chosen_layout == "Layout A"
