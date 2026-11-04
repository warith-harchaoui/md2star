"""Kawasaki 10/20/30 on the smart-layout path: ``--min-pt`` and everything it implies.

One file for the whole feature, grouped by what the author of a 30 pt course
deck needs from md2star:

* A — no slide text under the floor, the template's own sizes kept;
* B — no content silently dropped (truncation, cover body, notes, columns);
* C — explicit, deterministic layout hints that bypass the models;
* D — an eyeball loop that accumulates, says "unknown", and can be steered;
* E — speaker notes that keep their bullets;
* F — dark backgrounds and declared colours read from the template.

Offline throughout: python-pptx's bundled template (edited where a test needs
a designer's lstStyle), fake chat / render seams, no LibreOffice, no model.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")

from pptx.dml.color import RGBColor  # noqa: E402
from pptx.oxml.ns import qn  # noqa: E402
from pptx.util import Inches, Pt  # noqa: E402

from md2star import pptx_assemble as pa  # noqa: E402
from md2star import pptx_audit as au  # noqa: E402
from md2star import pptx_clone as pc  # noqa: E402
from md2star import pptx_fit as pf  # noqa: E402
from md2star import pptx_layout as pl  # noqa: E402


# ── fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def default_template(tmp_path: Path) -> Path:
    path = tmp_path / "default.pptx"
    pptx.Presentation().save(str(path))
    return path


@pytest.fixture
def catalog(default_template: Path) -> list[pl.LayoutInfo]:
    return pl.extract_layouts(default_template)


def _set_lvl1(placeholder, *, sz: int, rgb: str | None = None) -> None:
    """Give a layout placeholder an lstStyle level-1 size (and colour)."""
    body = placeholder._element.txBody
    lst = body.find(qn("a:lstStyle"))
    for child in list(lst):
        lst.remove(child)
    lvl = lst.makeelement(qn("a:lvl1pPr"), {})
    rpr = lvl.makeelement(qn("a:defRPr"), {"sz": str(sz)})
    if rgb:
        fill = rpr.makeelement(qn("a:solidFill"), {})
        fill.append(fill.makeelement(qn("a:srgbClr"), {"val": rgb}))
        rpr.append(fill)
    lvl.append(rpr)
    lst.append(lvl)


@pytest.fixture
def designer_template(tmp_path: Path) -> Path:
    """The stock template with a designer's 36 pt body declared on its layout."""
    prs = pptx.Presentation()
    layout = prs.slide_layouts.get_by_name("Title and Content")
    body = next(p for p in layout.placeholders if p.placeholder_format.idx == 1)
    _set_lvl1(body, sz=3600, rgb="123456")
    path = tmp_path / "designer.pptx"
    prs.save(str(path))
    return path


def _runs(slide):
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for para in shape.text_frame.paragraphs:
            for run in para.runs:
                yield shape, run


# ── A: the floor ─────────────────────────────────────────────────────────────
class TestMinPtRendering:
    def test_no_explicit_size_under_the_floor(self, tmp_path, default_template, catalog) -> None:
        slides = pl.segment("# Deck\n\n***\n\n## Points\n\n- a\n- b\n\n***\n\n## Fin\n")
        for s, name in zip(slides, ["Title Slide", "Title Only", "Title Only"], strict=True):
            s.chosen_layout = name
        out = tmp_path / "floor.pptx"
        pa.assemble(slides, catalog, default_template, out, min_pt=30)
        prs = pptx.Presentation(str(out))
        sizes = [run.font.size.pt for sl in prs.slides for _, run in _runs(sl) if run.font.size]
        assert sizes and min(sizes) >= 30

    def test_the_designer_size_is_inherited_not_overwritten(
        self, tmp_path, designer_template
    ) -> None:
        catalog = pl.extract_layouts(designer_template)
        slides = pl.segment("# Deck\n\n***\n\n## Points\n\n- alpha\n- beta\n\n***\n\n## Fin\n")
        slides[1].chosen_layout = "Title and Content"
        out = tmp_path / "inherit.pptx"
        pa.assemble(slides, catalog, designer_template, out, min_pt=30)
        slide = pptx.Presentation(str(out)).slides[1]
        body = next(s for s in slide.placeholders if s.placeholder_format.idx == 1)
        # Written INTO the designer's placeholder, without a "•" of ours,
        # without a size or a colour of ours: the layout's 36 pt and colour.
        assert body.text_frame.text == "alpha\nbeta"
        for para in body.text_frame.paragraphs:
            for run in para.runs:
                assert run.font.size is None
                assert run.font._rPr is None or run.font._rPr.find(qn("a:solidFill")) is None
        assert pa.declared_style(body)[0] == 36.0
        # And nothing is allowed to auto-shrink it.
        assert body.text_frame._bodyPr.find(qn("a:normAutofit")) is None

    def test_without_min_pt_the_historical_sizes_stand(
        self, tmp_path, default_template, catalog
    ) -> None:
        slides = pl.segment("# Deck\n\n***\n\n## Points\n\n- a\n\n***\n\n## Fin\n")
        slides[1].chosen_layout = "Title Only"
        out = tmp_path / "legacy.pptx"
        pa.assemble(slides, catalog, default_template, out)
        sizes = {
            run.font.size.pt
            for _, run in _runs(pptx.Presentation(str(out)).slides[1])
            if run.font.size
        }
        assert 16 in sizes

    def test_clone_floor_respects_min_pt(self) -> None:
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        box = slide.shapes.add_textbox(0, 0, Inches(4), Inches(1))
        box.text_frame.text = "x"
        box.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
        pc._enforce_floor(box, -4, 30)
        assert box.text_frame.paragraphs[0].runs[0].font.size.pt == 30


class TestAuditMinPt:
    def _deck(self, tmp_path: Path) -> Path:
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        h = prs.slide_height
        small = slide.shapes.add_textbox(Inches(1), Inches(1), Inches(6), Inches(2))
        small.text_frame.text = "content at sixteen"
        small.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
        footer = slide.shapes.add_textbox(Inches(1), int(h * 0.93), Inches(4), Inches(0.3))
        footer.text_frame.text = "Enterprise AI · deraison.ai"
        footer.text_frame.paragraphs[0].runs[0].font.size = Pt(10)
        num = slide.shapes.add_textbox(Inches(8), Inches(3), Inches(1), Inches(0.4))
        p = num.text_frame.paragraphs[0]
        fld = p._p.makeelement(
            qn("a:fld"), {"id": "{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}", "type": "slidenum"}
        )
        t = fld.makeelement(qn("a:t"), {})
        t.text = "1"
        fld.append(t)
        p._p.append(fld)
        path = tmp_path / "audit.pptx"
        prs.save(str(path))
        return path

    def test_content_under_the_floor_is_flagged_chrome_is_not(self, tmp_path: Path) -> None:
        findings = au.audit(self._deck(tmp_path), min_pt=30)
        flagged = [f for f in findings if f.kind == "under-min-pt"]
        assert [f.shape for f in flagged] == ["TextBox 1"]

    def test_nothing_is_reported_without_the_flag(self, tmp_path: Path) -> None:
        assert not [f for f in au.audit(self._deck(tmp_path)) if f.kind == "under-min-pt"]

    def test_run_fails_on_it(self, tmp_path: Path, capsys) -> None:
        assert au.run(str(self._deck(tmp_path)), min_pt=30) == 1

    def test_inherited_placeholder_sizes_are_measured(self, tmp_path: Path) -> None:
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        slide.placeholders[1].text_frame.text = "inherits the master's body size"
        path = tmp_path / "inherit.pptx"
        prs.save(str(path))
        # The stock master declares 32 pt body text: above 30, under 40.
        assert not [f for f in au.audit(path, min_pt=30) if f.kind == "under-min-pt"]
        assert [f for f in au.audit(path, min_pt=40) if f.kind == "under-min-pt"]


def _box_layout(name: str, height_in: float, *, title: bool = True) -> pl.LayoutInfo:
    phs = [pl.Placeholder(idx=0, kind="title", emu=(0, 0, 9 * 914400, 914400))] if title else []
    phs.append(
        pl.Placeholder(idx=1, kind="body", emu=(0, 914400, 9 * 914400, int(height_in * 914400)))
    )
    return pl.LayoutInfo(name=name, placeholders=phs)


class TestStrictRanking:
    def test_an_overflowing_slide_goes_somewhere_roomier(self) -> None:
        small, roomy = _box_layout("Small", 1.0), _box_layout("Roomy", 6.0)
        body = "## Many\n\n" + "\n".join(f"- point number {i} with a few words" for i in range(6))
        slides = [
            pl.Slide(index=1, title="Cover", title_only=True),
            pl.Slide(index=2, title="Many", body=body, features=["bullets"]),
        ]

        def chat(_prompt, _images, _schema):
            return {"choices": [{"index": 2, "layout_name": "Small", "why": "x"}]}

        pl.select_layouts(slides, [small, roomy], chat=chat, min_pt=30, strict=True)
        assert slides[1].chosen_layout == "Roomy"

    def test_overflow_under_min_pt_is_never_shrunk(self) -> None:
        assert pa._overrides_for({"overflow": True, "font_delta": -6}, min_pt=30) == {}


# ── B: nothing dropped ───────────────────────────────────────────────────────
class TestNothingDropped:
    def test_no_bullet_or_word_cap(self) -> None:
        body = "\n".join(f"- {' '.join(['word'] * 20)} {i}" for i in range(9))
        bullets = pa.fallback_bullets(body)
        assert len(bullets) == 9
        assert all(len(b.split()) == 21 for b in bullets)

    def test_nested_and_numbered_items_keep_their_shape(self) -> None:
        items = pa.body_items("- top\n  - nested\n1. first\n\nA plain sentence\nthat wraps.\n")
        assert [(i.text, i.level, i.bullet) for i in items] == [
            ("top", 0, True),
            ("nested", 1, True),
            ("1. first", 0, False),
            ("A plain sentence that wraps.", 0, False),
        ]

    def test_an_unfittable_slide_becomes_continuations(self) -> None:
        roomy = _box_layout("Only", 3.0)
        lines = "\n".join(f"- bullet {i} has quite a few words in it to fill" for i in range(14))
        slides = pl.segment(f"---\nlang: fr-FR\n---\n\n# Deck\n\n## Liste\n\n{lines}\n\n## Fin\n")
        out = pl.paginate(slides, [roomy], min_pt=30)
        titles = [s.title for s in out]
        assert titles[1] == "Liste" and titles[2] == "Liste (suite)"
        assert [s.index for s in out] == list(range(1, len(out) + 1))
        # Every bullet survives, exactly once, in order.
        kept = [b for s in out[1:-1] for b in pa.fallback_bullets(s.body)]
        assert kept == [f"bullet {i} has quite a few words in it to fill" for i in range(14)]

    def test_continuation_label_in_english(self) -> None:
        assert pl.continuation_label("en-US") == "(cont.)"
        assert pl.continuation_label("", "the cost and the value of the model") == "(cont.)"
        assert pl.continuation_label("", "le coût des erreurs est pour le client") == "(suite)"

    def test_cover_keeps_its_subtitle_and_front_matter(self) -> None:
        md = "---\ntitle: Deck\nsubtitle: Jour 1\nauthor: Ada\ndate: 2026-11-05\n---\n\n# Deck\n\n## A\n\n- x\n"
        cover = pl.segment(md)[0]
        assert cover.title_only and cover.subtitle == "Jour 1\nAda\n2026-11-05"

    def test_cover_prose_is_its_subtitle(self) -> None:
        cover = pl.segment("# Deck\n\nA one-line promise\n\n## A\n\n- x\n")[0]
        assert cover.subtitle == "A one-line promise"

    def test_a_front_matter_title_no_slide_carries_becomes_the_cover(self) -> None:
        slides = pl.segment(
            "---\ntitle: Enterprise AI\nsubtitle: Jour 1\n---\n\n# Part one\n\n## A\n\n- x\n"
        )
        assert [s.title for s in slides][:2] == ["Enterprise AI", "Part one"]
        assert slides[0].subtitle == "Jour 1"
        assert slides[1].title_only and slides[1].class_hint == "section"

    def test_notes_only_chunk_goes_to_the_previous_slide(self) -> None:
        md = "# D\n\n## A\n\n- x\n\n---\n\n::: notes\n- late note\n:::\n\n## B\n\n- y\n"
        slides = pl.segment(md)
        a = next(s for s in slides if s.title == "A")
        b = next(s for s in slides if s.title == "B")
        assert "late note" in a.notes and "late note" not in b.notes

    def test_cover_and_closing_with_bullets_keep_them(
        self, tmp_path, default_template, catalog
    ) -> None:
        slides = pl.segment("# Cover\n\n- one\n- two\n")
        slides[0].chosen_layout = "Title and Content"
        out = tmp_path / "cover.pptx"
        pa.assemble(slides, catalog, default_template, out)
        text = " ".join(
            sh.text_frame.text
            for sh in pptx.Presentation(str(out)).slides[0].shapes
            if sh.has_text_frame
        )
        assert "one" in text and "two" in text

    def test_tables_are_placed(self, tmp_path, default_template, catalog) -> None:
        slides = pl.segment("# D\n\n## T\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n## E\n")
        slides[1].chosen_layout = "Title Only"
        out = tmp_path / "table.pptx"
        pa.assemble(slides, catalog, default_template, out)
        tables = [sh for sh in pptx.Presentation(str(out)).slides[1].shapes if sh.has_table]
        assert tables and tables[0].table.cell(1, 1).text == "2"


class TestColumns:
    MD = (
        "# D\n\n## Two\n\n:::: {.columns}\n::: {.column}\n- left one\n- left two\n:::\n"
        "::: {.column}\n- right one\n:::\n::::\n\n## E\n"
    )

    def test_split_columns(self) -> None:
        cols = pa.split_columns(self.MD)
        assert len(cols) == 2 and "right one" in cols[1] and "left one" in cols[0]

    def test_feature_and_measure_see_the_columns(self) -> None:
        s = pl.segment(self.MD)[1]
        assert "two-column" in s.features
        assert pf.measure(s.title, s.body).columns == 2

    @pytest.mark.parametrize("min_pt", [None, 30])
    def test_both_columns_are_filled(self, tmp_path, default_template, catalog, min_pt) -> None:
        slides = pl.segment(self.MD)
        slides[1].chosen_layout = "Two Content"
        out = tmp_path / "cols.pptx"
        pa.assemble(slides, catalog, default_template, out, min_pt=min_pt)
        slide = pptx.Presentation(str(out)).slides[1]
        texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
        left = next(t for t in texts if "left one" in t)
        right = next(t for t in texts if "right one" in t)
        assert left != right and "right" not in left


# ── C: explicit hints ────────────────────────────────────────────────────────
class TestHints:
    def test_parse_heading(self) -> None:
        assert pl.parse_heading('73 % {.bignumber layout="Big Number"}') == (
            "73 %",
            ["bignumber"],
            "Big Number",
        )

    def test_a_layout_hint_pins_without_asking_the_model(self, catalog) -> None:
        slides = pl.segment(
            '# D\n\n## Pinned {layout="Two Content"}\n\n- a\n\n## Free\n\n- b\n\n## E\n'
        )
        prompts: list[str] = []

        def chat(prompt, _images, _schema):
            prompts.append(prompt)
            return None

        pl.select_layouts(slides, catalog, chat=chat)
        pinned = slides[1]
        assert pinned.title == "Pinned" and pinned.chosen_layout == "Two Content" and pinned.pinned
        assert prompts and "'Pinned'" not in prompts[0] and "'Free'" in prompts[0]

    def test_a_case_insensitive_name_is_accepted(self, catalog) -> None:
        s = pl.Slide(index=2, title="x", layout_hint="two content")
        assert pl.resolve_hint(s, catalog) == "Two Content"

    def test_an_unknown_layout_falls_back_to_selection(self, catalog) -> None:
        assert pl.resolve_hint(pl.Slide(index=2, title="x", layout_hint="Nope"), catalog) is None

    def test_class_shortcuts_resolve_by_name_then_archetype(self) -> None:
        cat = [
            pl.LayoutInfo(name="Recap"),
            pl.LayoutInfo(name="Plain Big", archetype="big-statement"),
        ]
        assert pl.resolve_hint(pl.Slide(index=2, title="x", class_hint="recap"), cat) == "Recap"
        assert (
            pl.resolve_hint(pl.Slide(index=2, title="x", class_hint="statement"), cat)
            == "Plain Big"
        )

    @pytest.mark.parametrize(
        "title",
        [
            "Qu'est-ce que nous avons appris",
            "Qu’est-ce que nous avons appris ?",
            "What we have learned",
            "Key takeaways",
            "Ce que nous avons appris",
        ],
    )
    def test_recap_titles(self, title) -> None:
        slides = pl.segment(f"# D\n\n## {title}\n\n- a\n\n## E\n")
        assert slides[1].class_hint == "recap"

    def test_class_from_heading(self) -> None:
        slides = pl.segment("# D\n\n## Stop {.statement}\n\nOne idea.\n\n## E\n")
        assert slides[1].title == "Stop" and slides[1].class_hint == "statement"

    def test_inferred_forms(self) -> None:
        md = (
            "# D\n\n## Fig\n\n**×18**\n\nfaster\n\n## Q\n\n> Cite me\n\n— Someone\n\n"
            "## S\n\nOne short claim.\n\n## L\n\n- a\n- b\n\n## E\n"
        )
        hints = {s.title: s.class_hint for s in pl.segment(md)}
        assert hints["Fig"] == "bignumber" and hints["Q"] == "quote"
        assert hints["S"] == "statement" and hints["L"] is None

    def test_h1_past_the_cover_is_a_section(self) -> None:
        slides = pl.segment("# Deck\n\n## A\n\n- x\n\n# Part two\n\n## B\n\n- y\n\n## E\n")
        part = next(s for s in slides if s.title == "Part two")
        assert part.level == 1 and part.title_only and part.class_hint == "section"

    def test_prompt_states_level_and_position(self, catalog) -> None:
        slides = pl.segment("# Deck\n\n## A\n\n- x\n- y\n\n## B\n\n- z\n- w\n")
        prompts: list[str] = []
        pl.select_layouts(slides, catalog, chat=lambda p, *_: prompts.append(p))
        assert "heading: H2 | position: 2/3 (middle)" in prompts[0]
        assert "position: 3/3 (last)" in prompts[0]


class TestSegmentation:
    def test_a_stray_rule_does_not_swallow_headings(self) -> None:
        slides = pl.segment("# D\n\n## A\n\n- a\n\n---\n\n## B\n\n- b\n\n## C\n\n- c\n")
        assert [s.title for s in slides] == ["D", "A", "B", "C"]

    def test_a_comment_in_code_is_not_a_heading(self) -> None:
        slides = pl.segment("# D\n\n## Code\n\n```python\n# not a slide\nx = 1\n```\n\n## E\n")
        assert [s.title for s in slides] == ["D", "Code", "E"]


# ── D: the eyeball loop ──────────────────────────────────────────────────────
class TestEyeballLoop:
    def _setup(self, default_template, catalog):
        slides = pl.segment("# C\n\n## Body\n\n- a\n- b\n\n## E\n")
        for s, n in zip(slides, ["Title Slide", "Title and Content", "Title Slide"], strict=True):
            s.chosen_layout = n
        for c in catalog:
            if c.name == "Title and Content":
                c.example_pages = [1]
        return slides

    def test_font_delta_accumulates(self) -> None:
        first = pa._overrides_for({"overflow": True, "font_delta": -2}, {})
        second = pa._overrides_for({"overflow": True, "font_delta": -2}, first)
        assert first["font_delta"] == -2 and second["font_delta"] == -4

    def test_a_silent_judge_is_unknown_not_a_match(
        self, tmp_path, default_template, catalog, monkeypatch
    ) -> None:
        slides = self._setup(default_template, catalog)
        monkeypatch.setattr(
            au,
            "audit",
            lambda _deck, **_kw: [
                au.Finding(2, "overrun", "x", "Body", measured_pt=16, fits_pt=14)
            ],
        )
        result = pa.eyeball_slides(
            slides,
            catalog,
            default_template,
            tmp_path / "e.pptx",
            indices=[2],
            max_iterations=1,
            chat=lambda *_a: None,  # the judge times out
            render_template=lambda *_a: b"target",
            render_deck=lambda _p: {2: b"candidate"},
        )
        assert 2 in result.unjudged
        # The measured verdict still drove the exact fix.
        assert slides[1].overrides.get("font_delta") == -2

    def test_min_pt_overflow_with_no_room_left_splits(
        self, tmp_path, default_template, catalog, monkeypatch
    ) -> None:
        slides = pl.segment("# C\n\n## Body\n\n- one\n- two\n- three\n- four\n\n## E\n")
        for s in slides:
            s.chosen_layout = "Title and Content"
        calls = {"n": 0}

        def fake_audit(_deck, **_kw):
            calls["n"] += 1
            return (
                [au.Finding(2, "overrun", "x", "Body", measured_pt=30, fits_pt=20)]
                if calls["n"] == 1
                else []
            )

        monkeypatch.setattr(au, "audit", fake_audit)
        pa.eyeball_slides(
            slides,
            catalog,
            default_template,
            tmp_path / "split.pptx",
            max_iterations=1,
            chat=lambda *_a: None,
            render_template=lambda *_a: None,
            render_deck=lambda _p: {},
            min_pt=30,
        )
        titles = [s.title for s in slides]
        assert titles[1] == "Body" and titles[2].startswith("Body (")
        assert [s.index for s in slides] == [1, 2, 3, 4]

    def test_env_overrides_the_model(self, monkeypatch) -> None:
        seen = {}

        def fake_chat(prompt, **kw):
            seen.update(kw)
            return "ok"

        monkeypatch.setenv("MD2STAR_VLM_MODEL", "qwen3-vl:8b")
        monkeypatch.setattr(pl.llm, "chat", fake_chat)
        monkeypatch.setattr(pl, "engine", lambda: {})
        pl.default_chat(kind="vlm")("p", None, None)
        assert seen["model"] == "qwen3-vl:8b"

    def test_visual_confirm_shows_the_current_pick_and_the_content(self) -> None:
        current = pl.LayoutInfo(name="Current", archetype="bulleted-content")
        other = pl.LayoutInfo(name="Other", archetype="photo-hero", example_pages=[3])
        s = pl.Slide(index=2, title="T", body="## T\n\n- alpha point\n", features=["bullets"])
        s.chosen_layout = "Current"
        seen: dict = {}

        def chat(prompt, images, _schema):
            seen["prompt"], seen["images"] = prompt, images
            return {"best": "Current"}

        pl.visual_confirm(
            [s],
            [current, other],
            chat=chat,
            render=lambda _t, page: b"page%d" % page,
            render_layout=lambda _t, name: f"layout-{name}".encode(),
            template=Path("t.pptx"),
        )
        assert b"layout-Current" in seen["images"]
        assert "Current" in seen["prompt"] and "alpha point" in seen["prompt"]

    def test_pinned_slides_skip_the_tie_break(self) -> None:
        s = pl.Slide(index=2, title="T", chosen_layout="A", pinned=True)

        def chat(*_a):
            raise AssertionError("a pinned slide must not be re-judged")

        pl.visual_confirm([s], [pl.LayoutInfo(name="A")], chat=chat, template=Path("t.pptx"))

    def test_refresh_bypasses_the_cache(self, tmp_path, default_template) -> None:
        cache = tmp_path / "cat.json"
        cache.write_text('[{"name": "Stale", "placeholders": []}]', encoding="utf-8")
        assert [
            c.name for c in pl.build_catalog(default_template, use_vision=False, cache_path=cache)
        ] == ["Stale"]
        fresh = pl.build_catalog(default_template, use_vision=False, cache_path=cache, refresh=True)
        assert "Title Slide" in [c.name for c in fresh]


# ── E: speaker notes ─────────────────────────────────────────────────────────
class TestNotes:
    def test_notes_paragraphs(self) -> None:
        notes = "- **Ouvrir** sur Zillow\n- Coût\n  - au tableau\n\nTransition."
        assert pa.notes_paragraphs(notes) == [
            ("• Ouvrir sur Zillow", 0),
            ("• Coût", 0),
            ("• au tableau", 1),
            ("Transition.", 0),
        ]

    def test_assembled_notes_are_paragraphs(self, tmp_path, default_template, catalog) -> None:
        slides = pl.segment(
            "# D\n\n## A\n\n- x\n\n::: notes\n- one\n- two\n  - deeper\n:::\n\n## E\n"
        )
        slides[1].chosen_layout = "Title and Content"
        out = tmp_path / "notes.pptx"
        pa.assemble(slides, catalog, default_template, out)
        frame = pptx.Presentation(str(out)).slides[1].notes_slide.notes_text_frame
        assert [p.text for p in frame.paragraphs] == ["• one", "• two", "• deeper"]
        assert [p.level for p in frame.paragraphs] == [0, 0, 1]


# ── F: backgrounds and colours ───────────────────────────────────────────────
class TestBackgrounds:
    def test_a_dark_master_background_is_seen(self) -> None:
        prs = pptx.Presentation()
        master = prs.slide_master
        master.background.fill.solid()
        master.background.fill.fore_color.rgb = RGBColor(0x10, 0x10, 0x10)
        layout = prs.slide_layouts[1]
        assert pa.is_dark_layout(layout) is True

    def test_theme_background_resolves(self) -> None:
        # The stock master's background is a theme reference (bg1 -> lt1).
        layout = pptx.Presentation().slide_layouts[1]
        assert pa.background_rgb(layout) == RGBColor(0xFF, 0xFF, 0xFF)
        assert pa.is_dark_layout(layout) is False

    def test_declared_colour_is_kept(self, tmp_path, designer_template) -> None:
        catalog = pl.extract_layouts(designer_template)
        slides = pl.segment("# D\n\n## A\n\n- alpha\n\n## E\n")
        slides[1].chosen_layout = "Title and Content"
        out = tmp_path / "colour.pptx"
        pa.assemble(slides, catalog, designer_template, out)  # legacy mode, overlay box
        slide = pptx.Presentation(str(out)).slides[1]
        colours = {
            str(run.font.color.rgb)
            for shape, run in _runs(slide)
            if "alpha" in run.text and run.font.color and run.font.color.type is not None
        }
        assert colours == {"123456"}


def test_cli_offers_the_new_flags(capsys) -> None:
    from md2star import cli

    try:
        cli.main(["pptx", "--help"])
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert "--min-pt" in out and "--refresh-catalog" in out


def test_deepcopy_slide_is_harmless() -> None:
    # Slides are plain dataclasses; the new fields must not break copying.
    s = pl.Slide(index=1, title="x", layout_hint="A", class_hint="recap", subtitle="y")
    assert copy.deepcopy(s).subtitle == "y"
