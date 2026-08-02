"""
Tests for the Markdown *twin* — the richer reverse path.

Two layers, both exercised **offline** (no Kreuzberg, no Ollama, no mmdc):

* ``md2star.reverse`` — the deterministic core: asset-name derivation, image
  placeholder resolution / stripping, and the ``to_markdown_twin`` writer, all
  driven through a monkeypatched ``extract_twin`` so no engine is needed.
* ``md2star.reverse_diagrams`` — the AI layer: the parse helpers and the
  target-matching eyeball loop are driven with **injected fakes** for the
  vision/text transport and the renderer, mirroring tests/test_ollama_client.py.

A live round-trip (real Kreuzberg image extraction) is covered separately and
skipped cleanly when the optional engine is absent.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from md2star import reverse, reverse_diagrams

_HAS_KREUZBERG = importlib.util.find_spec("kreuzberg") is not None


# ── deterministic core ───────────────────────────────────────────────────────


class TestTwinCore:
    """Asset naming, placeholder resolution, and the twin writer."""

    def test_suggested_name_is_stable_and_typed(self) -> None:
        img = reverse.TwinImage(data=b"x", format="PNG", image_index=2, page_number=3)
        # Page + index keyed, extension lower-cased and de-dotted → stable diffs.
        assert img.suggested_name == "img-p3-2.png"

    def test_default_handler_writes_png_and_links(self, tmp_path: Path) -> None:
        assets = tmp_path / "assets"
        img = reverse.TwinImage(data=b"\x89PNG", format="png", image_index=0, page_number=1)
        snippet = reverse._default_image_handler(img, assets)
        assert snippet == "![](assets/img-p1-0.png)"
        assert (assets / "img-p1-0.png").read_bytes() == b"\x89PNG"

    def test_resolve_images_replaces_placeholder(self, tmp_path: Path) -> None:
        img = reverse.TwinImage(data=b"z", format="png", image_index=0, page_number=1)
        md = "Intro\n\n![](image_0.png)\n\nOutro\n"
        out = reverse._resolve_images(md, [img], tmp_path / "assets", reverse._default_image_handler)
        assert "![](assets/img-p1-0.png)" in out
        assert "image_0.png" not in out  # the placeholder is gone

    def test_resolve_images_appends_orphans(self, tmp_path: Path) -> None:
        # An image with no matching placeholder must still land, under a section.
        img = reverse.TwinImage(data=b"z", format="png", image_index=7, page_number=2)
        out = reverse._resolve_images(
            "Body with no placeholder\n", [img], tmp_path / "assets", reverse._default_image_handler
        )
        assert "## Extracted figures" in out
        assert "![](assets/img-p2-7.png)" in out

    def test_strip_placeholders_removes_markers(self) -> None:
        img = reverse.TwinImage(data=b"z", format="png", image_index=0, page_number=1)
        out = reverse._strip_placeholders("a\n\n![](image_0.png)\n\nb\n", [img])
        assert "image_0.png" not in out
        assert "a" in out and "b" in out

    def test_to_markdown_twin_writes_md_and_assets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Drive the writer without any engine: a canned extraction with one image.
        img = reverse.TwinImage(data=b"IMG", format="png", image_index=0, page_number=1)
        canned = reverse.TwinExtraction(markdown="# Doc\n\n![](image_0.png)\n", images=[img])
        monkeypatch.setattr(reverse, "extract_twin", lambda _p: canned)

        src = tmp_path / "report.pdf"
        src.write_bytes(b"%PDF-1.4 dummy")
        out = tmp_path / "twin"
        md_path = reverse.to_markdown_twin(src, out)

        assert md_path == out / "report.md"
        body = md_path.read_text(encoding="utf-8")
        assert "# Doc" in body
        assert "![](assets/img-p1-0.png)" in body
        assert (out / "assets" / "img-p1-0.png").read_bytes() == b"IMG"

    def test_to_markdown_twin_no_images_strips(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        img = reverse.TwinImage(data=b"IMG", format="png", image_index=0, page_number=1)
        canned = reverse.TwinExtraction(markdown="# Doc\n\n![](image_0.png)\n", images=[img])
        monkeypatch.setattr(reverse, "extract_twin", lambda _p: canned)

        src = tmp_path / "report.pdf"
        src.write_bytes(b"%PDF dummy")
        md_path = reverse.to_markdown_twin(src, tmp_path / "twin", extract_images=False)
        body = md_path.read_text(encoding="utf-8")
        assert "image_0.png" not in body
        assert not (tmp_path / "twin" / "assets").exists()


# ── AI diagram layer (offline, fakes injected) ───────────────────────────────


class TestDiagramParsing:
    """The tolerant parse helpers used to read model replies."""

    def test_extract_mermaid_from_fenced_block(self) -> None:
        got = reverse_diagrams._extract_mermaid("```mermaid\nflowchart LR\n A-->B\n```")
        assert got == "flowchart LR\n A-->B"

    def test_extract_mermaid_none_on_empty(self) -> None:
        assert reverse_diagrams._extract_mermaid("") is None

    def test_extract_svg_from_element(self) -> None:
        # The <svg> element is pulled out regardless of surrounding prose/fences.
        got = reverse_diagrams._extract_svg('Sure:\n```svg\n<svg viewBox="0 0 1 1"><rect/></svg>\n```')
        assert got == '<svg viewBox="0 0 1 1"><rect/></svg>'

    def test_extract_svg_none_without_element(self) -> None:
        # No <svg> element → unusable (unlike Mermaid, there is no bare fallback).
        assert reverse_diagrams._extract_svg("no vector here") is None
        assert reverse_diagrams._extract_svg("") is None

    def test_parse_verdict_true(self) -> None:
        v = reverse_diagrams._parse_verdict('{"matches": true, "discrepancies": ""}')
        assert v.matches is True

    def test_parse_verdict_false_with_notes(self) -> None:
        v = reverse_diagrams._parse_verdict('noise {"matches": false, "discrepancies": "no C"} x')
        assert v.matches is False and "no C" in v.discrepancies

    def test_parse_verdict_unparseable_is_no_match(self) -> None:
        assert reverse_diagrams._parse_verdict("¯\\_(ツ)_/¯").matches is False


class TestEyeballLoop:
    """The target-matching render → compare → revise loop, with injected fakes."""

    def test_converges_after_revision(self) -> None:
        state = {"compares": 0}

        def vlm(prompt: str, images: list[str]) -> str:
            if "Reproduce it as a Mermaid" in prompt:
                return "```mermaid\nflowchart LR\n A-->B\n```"
            if "FIRST image" in prompt:
                state["compares"] += 1
                # First comparison fails; after one revision it matches.
                if state["compares"] == 1:
                    return '{"matches": false, "discrepancies": "missing C"}'
                return '{"matches": true, "discrepancies": ""}'
            if "Fix the Mermaid" in prompt:
                return "```mermaid\nflowchart LR\n A-->B\n B-->C\n```"
            return ""

        src = reverse_diagrams.reconstruct_mermaid(
            "target.png", vlm=vlm, render=lambda _k, _s: "cand.png", max_iterations=3
        )
        assert src is not None and "B-->C" in src

    def test_unrenderable_returns_best_draft(self) -> None:
        # No renderer output → cannot verify; the first draft is returned as-is.
        def vlm(prompt: str, images: list[str]) -> str:
            return "```mermaid\nflowchart LR\n A-->B\n```" if "Reproduce" in prompt else ""

        src = reverse_diagrams.reconstruct_mermaid(
            "t.png", vlm=vlm, render=lambda _k, _s: None, max_iterations=3
        )
        assert src == "flowchart LR\n A-->B"

    def test_no_draft_returns_none(self) -> None:
        src = reverse_diagrams.reconstruct_mermaid(
            "t.png", vlm=lambda _p, _i: "", render=lambda _k, _s: "c.png"
        )
        assert src is None

    def test_reconstruct_svg_converges(self) -> None:
        # The same loop drives SVG: draft → compare (fail) → revise → match.
        state = {"compares": 0}

        def vlm(prompt: str, images: list[str]) -> str:
            if "self-contained SVG" in prompt:
                return '<svg viewBox="0 0 2 2"><circle r="1"/></svg>'
            if "FIRST image" in prompt:
                state["compares"] += 1
                if state["compares"] == 1:
                    return '{"matches": false, "discrepancies": "wrong colour"}'
                return '{"matches": true, "discrepancies": ""}'
            if "Fix the SVG" in prompt:
                return '<svg viewBox="0 0 2 2"><circle r="1" fill="red"/></svg>'
            return ""

        src = reverse_diagrams.reconstruct_svg(
            "target.png", vlm=vlm, render=lambda _k, _s: "cand.png", max_iterations=3
        )
        assert src is not None and 'fill="red"' in src


class TestDiagramHandler:
    """Photo-vs-diagram routing via make_diagram_handler with fakes."""

    def test_diagram_emits_mermaid_and_keeps_png(self, tmp_path: Path) -> None:
        def vlm(prompt: str, images: list[str]) -> str:
            if "triaging" in prompt:
                return "DIAGRAM"
            if "Reproduce it as a Mermaid" in prompt:
                return "```mermaid\nflowchart LR\n X-->Y\n```"
            if "FIRST image" in prompt:
                return '{"matches": true, "discrepancies": ""}'
            return ""

        handler = reverse_diagrams.make_diagram_handler(vlm=vlm, render=lambda _k, _s: "c.png")
        img = reverse.TwinImage(data=b"PNG", format="png", image_index=0, page_number=1)
        md = handler(img, tmp_path / "assets")
        assert "```mermaid" in md and "X-->Y" in md
        assert "<!-- source figure:" in md  # PNG fallback preserved
        assert (tmp_path / "assets" / "img-p1-0.png").exists()

    def test_figure_emits_svg_and_keeps_png(self, tmp_path: Path) -> None:
        def vlm(prompt: str, images: list[str]) -> str:
            if "triaging" in prompt:
                return "FIGURE"
            if "self-contained SVG" in prompt:
                return '<svg viewBox="0 0 4 4"><rect width="4" height="4"/></svg>'
            if "FIRST image" in prompt:
                return '{"matches": true, "discrepancies": ""}'
            return ""

        handler = reverse_diagrams.make_diagram_handler(vlm=vlm, render=lambda _k, _s: "c.png")
        img = reverse.TwinImage(data=b"PNG", format="png", image_index=0, page_number=1)
        md = handler(img, tmp_path / "assets")
        # The vector is linked as the primary asset; the scraped PNG rides along.
        assert "![](assets/img-p1-0.svg)" in md
        assert "<!-- source figure:" in md
        assert (tmp_path / "assets" / "img-p1-0.svg").read_text().startswith("<svg")
        assert (tmp_path / "assets" / "img-p1-0.png").exists()

    def test_figure_falls_back_to_png_when_no_svg(self, tmp_path: Path) -> None:
        # Classified FIGURE but the model never emits an <svg> → keep the PNG.
        def vlm(prompt: str, images: list[str]) -> str:
            return "FIGURE" if "triaging" in prompt else "sorry, no vector"

        handler = reverse_diagrams.make_diagram_handler(vlm=vlm, render=lambda _k, _s: "c.png")
        img = reverse.TwinImage(data=b"PNG", format="png", image_index=2, page_number=3)
        md = handler(img, tmp_path / "assets")
        assert md == "![](assets/img-p3-2.png)"
        assert not (tmp_path / "assets" / "img-p3-2.svg").exists()

    def test_photo_keeps_png_only(self, tmp_path: Path) -> None:
        handler = reverse_diagrams.make_diagram_handler(
            vlm=lambda _p, _i: "PHOTO", render=lambda _k, _s: None
        )
        img = reverse.TwinImage(data=b"PNG", format="png", image_index=1, page_number=2)
        md = handler(img, tmp_path / "assets")
        assert md == "![](assets/img-p2-1.png)"

    def test_ambiguous_classification_defaults_to_photo(self, tmp_path: Path) -> None:
        # An empty/odd classifier reply must not trigger a wasted reconstruction.
        handler = reverse_diagrams.make_diagram_handler(
            vlm=lambda _p, _i: "", render=lambda _k, _s: "c.png"
        )
        img = reverse.TwinImage(data=b"PNG", format="png", image_index=0, page_number=0)
        md = handler(img, tmp_path / "assets")
        assert md.startswith("![](")


# ── live round-trip (skipped without the optional engine) ────────────────────


@pytest.mark.slow
@pytest.mark.skipif(not _HAS_KREUZBERG, reason="twin extraction needs the [ocr] engine")
class TestLiveExtraction:
    """A real Kreuzberg extraction over a generated image-bearing PDF."""

    def test_twin_scrapes_embedded_image(self, tmp_path: Path) -> None:
        pytest.importorskip("matplotlib")
        import matplotlib

        matplotlib.use("Agg")
        import numpy as np
        from matplotlib.backends.backend_pdf import PdfPages

        pdf = tmp_path / "fixture.pdf"
        with PdfPages(pdf) as pp:
            import matplotlib.pyplot as plt

            fig = plt.figure(figsize=(6, 8))
            fig.text(0.1, 0.9, "Twin fixture", fontsize=18)
            ax = fig.add_axes([0.1, 0.4, 0.4, 0.3])
            ax.imshow(np.random.default_rng(0).random((40, 60, 3)))
            ax.axis("off")
            pp.savefig(fig)
            plt.close(fig)

        out = tmp_path / "twin"
        md_path = reverse.to_markdown_twin(pdf, out)
        assert md_path.is_file()
        # At least one raster was scraped into assets and linked from the body.
        assets = list((out / "assets").glob("*.png"))
        assert assets, "expected at least one scraped PNG"
        assert "assets/" in md_path.read_text(encoding="utf-8")
