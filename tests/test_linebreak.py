"""Semantic line breaking (:mod:`md2star.linebreak`): where a slide's lines end.

Deterministic throughout: the 0.55 em fallback metrics unless a test says
otherwise, so the suite does not depend on which fonts a machine carries.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from md2star import linebreak as lb


def _ends(lines: list[str]) -> list[str]:
    return [ln.split()[-1].lower() for ln in lines[:-1]]


def _starts(lines: list[str]) -> list[str]:
    return [ln.split()[0] for ln in lines[1:]]


@pytest.mark.parametrize("width", [300, 360, 420, 520])
def test_a_line_never_ends_on_a_function_word(width) -> None:
    for text in (
        "Ce que nous avons vraiment collecté",
        "La malédiction de la dimension nous attend au tournant de la route",
        "The cost of a mistake is not the same in both directions",
        "Une unité normalisée pour chaque cas qui paie",
    ):
        lines = lb.wrap(text, 30, width)
        assert " ".join(lines) == text
        assert not set(_ends(lines)) & lb.GLUE_AFTER, lines


@pytest.mark.parametrize("width", [200, 240, 280, 330])
def test_a_line_never_starts_with_a_colon_nor_splits_a_number(width) -> None:
    lines = lb.wrap("des exemples énormes : la malédiction", 30, width)
    assert ":" not in _starts(lines), lines
    lines = lb.wrap("2 min gagnées sur 500 000 examens", 30, width)
    joined = "|".join(lines)
    assert "2 min" in joined and "500 000" in joined, lines
    lines = lb.wrap("une hausse de 30 % des dossiers traités", 30, width)
    assert "%" not in _starts(lines), lines


def test_no_orphan_word_on_the_last_line() -> None:
    lines = lb.wrap("Ce qui casse est rarement le modèle lui-même", 30, 330)
    assert len(lines[-1].split()) > 1, lines


def test_breaking_after_punctuation_is_preferred() -> None:
    lines = lb.wrap("Vous ne pilotez pas : vous fixez les seuils", 30, 380)
    assert lines[0].endswith(":"), lines


def test_what_fits_is_left_alone_spaces_included() -> None:
    assert lb.wrap("•  court", 30, 400) == ["•  court"]
    assert lb.wrap("   •  un deux trois quatre cinq six sept", 30, 260)[0].startswith("   •  ")


def test_break_lines_writes_vertical_tabs_and_drops_a_missing_nbsp() -> None:
    out = lb.break_lines("2 min gagnées sur 500 000 examens", 30, 260)
    assert "\v" in out and " " not in out and " " not in out
    assert "2 min" in out and "500 000" in out


@pytest.mark.skipif(
    lb.face("Satoshi") is None, reason="the course face is not installed on this machine"
)
def test_real_metrics_are_read_from_the_font_file() -> None:
    m = lb.face("Satoshi")
    assert lb.width("W", 30, m) > lb.width("i", 30, m)
    assert not lb.has_glyph(m, " ")  # why NBSP cannot be relied on


def test_titles_and_bullets_are_written_with_their_breaks(tmp_path: Path) -> None:
    pptx = pytest.importorskip("pptx")
    from md2star import pptx_assemble as pa
    from md2star import pptx_layout as pl

    template = tmp_path / "t.pptx"
    pptx.Presentation().save(str(template))
    catalog = pl.extract_layouts(template)
    md = (
        "# D\n\n## Ce que nous avons vraiment collecté auprès de tous les services\n\n"
        "- des exemples énormes : la malédiction de la dimension nous attend\n"
        "- 2 min gagnées sur 500 000 examens, soit des milliers d'heures\n\n"
        "::: notes\nune note assez longue pour être coupée si on la coupait, "
        "ce qui ne doit jamais arriver\n:::\n\n## E\n"
    )
    slides = pl.segment(md)
    slides[1].chosen_layout = "Title and Content"
    out = tmp_path / "o.pptx"
    pa.assemble(slides, catalog, template, out, min_pt=30)
    slide = pptx.Presentation(str(out)).slides[1]
    texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
    broken = [t for t in texts if "\v" in t]
    assert broken, texts
    for t in texts:
        for para in t.split("\n"):
            lines = para.split("\v")
            assert not set(_ends(lines)) & lb.GLUE_AFTER, lines
            assert ":" not in _starts(lines)
    assert "\v" not in slide.notes_slide.notes_text_frame.text
