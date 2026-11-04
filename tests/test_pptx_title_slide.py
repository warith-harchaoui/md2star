"""Regression tests for the plain Pandoc PPTX path's title slide.

Two defects, both observed on a real course deck converted with
``md2pptx deck.md --reference-doc T.pptx`` (no ``--smart-layout``):

* With ``title`` in the front matter, the first ``# Part`` heading was taken
  for the title, dropped, and the auto-dated subtitle Div was put in its
  place: slide 2 became a "Title and Content" slide reading "Mercredi 4
  novembre 2026" instead of the "Section Header" slide the author wrote.
* Pandoc ends the title slide's subtitle with one ``<a:br/>`` per missing
  author/date line, so the subtitle shipped as ``"Jour 1 · Comprendre\\v\\v"``.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")

from md2star import postprocess  # noqa: E402
from md2star.pipeline import ConvertOptions, convert  # noqa: E402

needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")

DECK = """---
title: Enterprise AI
subtitle: Jour 1 · Comprendre
lang: fr-FR
---

# Le coût des erreurs

## Qui paie l'erreur ?

- Le client
- L'entreprise
"""


def _slides(path: Path) -> list[tuple[str, list[str]]]:
    prs = pptx.Presentation(str(path))
    return [
        (s.slide_layout.name, [sh.text_frame.text for sh in s.shapes if sh.has_text_frame])
        for s in prs.slides
    ]


def _convert(tmp_path: Path, markdown: str, **opts) -> Path:
    src = tmp_path / "deck.md"
    src.write_text(markdown, encoding="utf-8")
    out = tmp_path / "deck.pptx"
    rc = convert(
        "pptx",
        ConvertOptions(
            input=str(src), output=str(out), offline=True, no_remote_templates=True, **opts
        ),
    )
    assert rc == 0
    return out


@needs_pandoc
class TestFrontMatterTitle:
    def test_first_h1_stays_a_section_header(self, tmp_path: Path) -> None:
        slides = _slides(_convert(tmp_path, DECK))
        titles = [" ".join(texts) for _, texts in slides]
        assert any("Le coût des erreurs" in t for t in titles)
        assert slides[1][0] == "Section Header"

    def test_no_auto_date_on_a_deck(self, tmp_path: Path) -> None:
        slides = _slides(_convert(tmp_path, DECK))
        everything = " ".join(" ".join(texts) for _, texts in slides)
        assert not re.search(r"\b20\d\d\b", everything)

    def test_subtitle_has_no_trailing_empty_lines(self, tmp_path: Path) -> None:
        cover = _slides(_convert(tmp_path, DECK))[0][1]
        subtitle = next(t for t in cover if "Jour 1" in t)
        assert subtitle == subtitle.rstrip("\x0b\n ")

    def test_explicit_date_reaches_the_cover(self, tmp_path: Path) -> None:
        cover = _slides(_convert(tmp_path, DECK, date="Jour 2"))[0][1]
        assert any("Jour 2" in t for t in cover)


class TestTrailingBreaks:
    def test_xml_strip_keeps_inner_breaks(self) -> None:
        xml = b"<a:p><a:r><a:t>a</a:t></a:r><a:br/><a:r><a:t>b</a:t></a:r><a:br /><a:br><a:rPr/></a:br></a:p>"
        new, changed = postprocess._strip_trailing_breaks_xml(xml)
        assert changed
        assert new == b"<a:p><a:r><a:t>a</a:t></a:r><a:br/><a:r><a:t>b</a:t></a:r></a:p>"

    def test_clean_xml_is_untouched(self) -> None:
        xml = b"<a:p><a:r><a:t>a</a:t></a:r></a:p>"
        assert postprocess._strip_trailing_breaks_xml(xml) == (xml, False)
