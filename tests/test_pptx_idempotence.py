"""Fixed points of the ``--smart-layout`` path.

`test_idempotence.py` proves run-to-run determinism of the **Pandoc** path and
is gated on Pandoc; this module proves the same discipline for the Seam-D
assembler, which needs `python-pptx` and no Pandoc at all — hence a separate
file rather than a second mark on that one. Four properties, in rising order
of what they are worth:

1. **The parsers are fixed points.** Lifting the metadata block and the
   speaker notes off a document a second time finds nothing left to lift.
2. **Assembly is pure.** Building the same deck twice gives the same shapes,
   in the same places, with the same text, and leaves the `Slide` objects as
   it found them (no override or tried-layout state accumulating across runs).
3. **Cleanup converges.** `drop_empty_placeholders` removes nothing the second
   time; running it is safe at any point.
4. **The assembler passes its own auditor.** `audit(assemble(x))` is empty.
   This is the one that earns its keep: it is a contract between two modules
   that are free to drift apart, and it fails loudly the day the assembler
   starts emitting something :mod:`md2star.pptx_audit` would complain about.

All offline and model-free: a synthetic template, a generated image, no
LibreOffice, no Ollama, no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")
PIL = pytest.importorskip("PIL")

from md2star import pptx_assemble as pa  # noqa: E402
from md2star import pptx_audit as au  # noqa: E402
from md2star import pptx_layout as pl  # noqa: E402

#: One slide of every kind the assembler branches on: a cover, bullets (with
#: notes, so the notes path is exercised), a picture, and a closing divider.
_SRC = """\
---
title: Quarterly Review
author: Jane Roe
---

# Quarterly Review

***

## Where we stand

- Revenue up 18% year on year
- Churn flat at 2.1%

::: notes
Provisional until the audit closes.
:::

***

## Revenue by segment

![Revenue climbing through Q3](chart.png)

***

## Thank you
"""

#: Layout per slide, pinned rather than selected: layout *choice* needs a
#: model, and these tests are about what the assembler does with a decision,
#: not about how the decision is reached.
_PLAN = ["Title Slide", "Title and Content", "Picture with Caption", "Section Header"]


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A directory holding a stock template and the image the deck references."""
    from PIL import Image

    pptx.Presentation().save(str(tmp_path / "template.pptx"))
    Image.new("RGB", (1600, 900), (20, 60, 120)).save(tmp_path / "chart.png")
    return tmp_path


def _build(workspace: Path, tag: str) -> tuple[Path, list[pl.Slide]]:
    """Assemble the fixture deck once; returns its path and the slide models."""
    template = workspace / "template.pptx"
    slides = pl.segment(_SRC)
    for slide, layout in zip(slides, _PLAN, strict=True):
        slide.chosen_layout = layout
    out = workspace / f"deck-{tag}.pptx"
    pa.assemble(slides, pl.extract_layouts(template), template, out, image_base_dir=workspace)
    return out, slides


def _inventory(deck: Path) -> list[tuple]:
    """Every shape that ended up in the file, with position, text and notes.

    Deliberately not a byte comparison: OOXML embeds timestamps and part ids,
    so two runs are never byte-identical and that is not the property worth
    testing. What must not drift is *what is on the slides*.
    """
    rows: list[tuple] = []
    for index, slide in enumerate(pptx.Presentation(str(deck)).slides, start=1):
        for shape in slide.shapes:
            rows.append(
                (
                    index,
                    shape.name,
                    pa.placeholder_kind(shape),
                    shape.left,
                    shape.top,
                    shape.width,
                    shape.height,
                    shape.text_frame.text if shape.has_text_frame else "",
                )
            )
        notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
        rows.append((index, "<notes>", "", 0, 0, 0, 0, notes))
    return rows


# ── 1. the parsers ───────────────────────────────────────────────────────────
class TestParsersAreFixedPoints:
    def test_lifting_the_metadata_block_twice_changes_nothing(self) -> None:
        once, meta = pl.split_front_matter(_SRC)
        twice, again = pl.split_front_matter(once)
        assert meta["title"] == "Quarterly Review"
        assert twice == once
        assert again == {}

    def test_lifting_the_notes_twice_changes_nothing(self) -> None:
        visible, notes = pl.split_notes(_SRC)
        assert notes  # the fixture has some, so this is not vacuous
        assert pl.split_notes(visible) == (visible, "")

    def test_segmenting_the_same_source_twice_gives_the_same_slides(self) -> None:
        first = [(s.index, s.title, s.body, s.notes, s.features) for s in pl.segment(_SRC)]
        second = [(s.index, s.title, s.body, s.notes, s.features) for s in pl.segment(_SRC)]
        assert first == second


# ── 2. assembly ──────────────────────────────────────────────────────────────
class TestAssemblyIsPure:
    def test_two_runs_put_the_same_things_in_the_same_places(self, workspace: Path) -> None:
        first, _ = _build(workspace, "a")
        second, _ = _build(workspace, "b")
        assert _inventory(first) == _inventory(second)

    def test_assembling_does_not_write_state_back_onto_the_slides(self, workspace: Path) -> None:
        """Only the eyeball loop may write `overrides` / `tried_layouts`.

        If assembly started accumulating either, a second pass over the same
        models would quietly produce a different deck — the exact drift the
        inventory check above would then be unable to explain.
        """
        _, slides = _build(workspace, "state")
        assert [s.overrides for s in slides] == [{}] * len(slides)
        assert [s.tried_layouts for s in slides] == [[]] * len(slides)


# ── 3. cleanup ───────────────────────────────────────────────────────────────
class TestCleanupConverges:
    def test_dropping_empty_placeholders_is_idempotent(self, workspace: Path) -> None:
        deck, _ = _build(workspace, "drop")
        presentation = pptx.Presentation(str(deck))
        assert [pa.drop_empty_placeholders(s) for s in presentation.slides] == [0] * 4


# ── 4. the contract between the assembler and the auditor ────────────────────
class TestTheAssemblerPassesItsOwnAuditor:
    def test_a_freshly_assembled_deck_is_clean(self, workspace: Path) -> None:
        deck, _ = _build(workspace, "audit")
        assert au.audit(deck) == []

    def test_auditing_is_pure(self, workspace: Path) -> None:
        """Same findings twice, and the file is not touched by looking at it."""
        deck, _ = _build(workspace, "pure")
        before = deck.read_bytes()
        assert au.audit(deck) == au.audit(deck)
        assert deck.read_bytes() == before
