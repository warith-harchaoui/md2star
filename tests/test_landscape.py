"""Keep LANDSCAPE / PAYSAGE and their CSVs telling the same story.

The star tables in `LANDSCAPE.md` / `PAYSAGE.md` are what a reader sees; the
CSVs in `assets/` are what `scripts/positioning.py` turns into the committed
positioning maps. Nothing but discipline keeps the two in step, and a drift is
silent in the worst way: the figure keeps rendering, it just plots ratings the
document no longer claims. These tests make that drift fail the build instead.

Pure stdlib and pure text — no standpoint, no model, no figure rendering.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent

#: Each document and the CSV whose ratings it must reproduce star for star.
_PAIRS = [
    ("LANDSCAPE.md", "assets/landscape.csv"),
    ("PAYSAGE.md", "assets/paysage.csv"),
]

_TABLE_RE = re.compile(r"<!-- TABLE:START -->(.*?)<!-- TABLE:END -->", re.DOTALL)


def _markdown_table(doc: str) -> list[list[str]]:
    """Rows of the fenced star table as ``[name, "⭐⭐", ...]``, header first."""
    match = _TABLE_RE.search((_ROOT / doc).read_text(encoding="utf-8"))
    assert match, f"{doc}: no <!-- TABLE:START --> … <!-- TABLE:END --> block"
    rows = []
    for line in match.group(1).strip().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        # The alignment row (`| --- | :---: | …`) carries no data.
        if all(set(c) <= set(":- ") for c in cells):
            continue
        rows.append([c.replace("**", "") for c in cells])
    return rows


def _csv_rows(path: str) -> list[list[str]]:
    with (_ROOT / path).open(encoding="utf-8") as handle:
        return [row for row in csv.reader(handle) if row]


@pytest.mark.parametrize(("doc", "data"), _PAIRS)
class TestTableMatchesCsv:
    def test_same_criteria_in_the_same_order(self, doc: str, data: str) -> None:
        assert _markdown_table(doc)[0] == _csv_rows(data)[0]

    def test_same_tools_in_the_same_order(self, doc: str, data: str) -> None:
        """Order matters: the CSV's first data row anchors the map top-right."""
        md_names = [row[0] for row in _markdown_table(doc)[1:]]
        csv_names = [row[0] for row in _csv_rows(data)[1:]]
        assert md_names == csv_names

    def test_every_rating_matches(self, doc: str, data: str) -> None:
        """A star count in the document is the integer in the CSV."""
        for md_row, csv_row in zip(_markdown_table(doc)[1:], _csv_rows(data)[1:], strict=True):
            stars = [len(cell) for cell in md_row[1:]]
            assert stars == [int(v) for v in csv_row[1:]], md_row[0]

    def test_ratings_are_one_to_five(self, doc: str, data: str) -> None:
        for row in _csv_rows(data)[1:]:
            assert all(1 <= int(v) <= 5 for v in row[1:]), row[0]

    def test_md2star_is_the_reference_row(self, doc: str, data: str) -> None:
        """scripts/positioning.py anchors the map on this name."""
        assert _csv_rows(data)[1][0] == "md2star"


def test_the_two_languages_rate_the_same_tools_identically() -> None:
    """Same ratings, same order, whatever the column headers are called.

    Only the row *labels* may be translated (``Obsidian export`` /
    ``Export Obsidian``); a rating that differs between the two documents would
    mean one of them is simply out of date.
    """
    en = _csv_rows("assets/landscape.csv")[1:]
    fr = _csv_rows("assets/paysage.csv")[1:]
    assert [row[1:] for row in en] == [row[1:] for row in fr]


@pytest.mark.parametrize("doc", [pair[0] for pair in _PAIRS])
def test_the_criteria_count_in_the_prose_is_right(doc: str) -> None:
    """The figure caption and the legend both state how many criteria there are."""
    text = (_ROOT / doc).read_text(encoding="utf-8")
    count = len(_markdown_table(doc)[0]) - 1  # minus the tool-name column
    words = {10: ("ten", "dix"), 11: ("eleven", "onze"), 12: ("twelve", "douze")}
    assert count in words, f"add the spelled-out form of {count} to this test"
    assert any(word in text for word in words[count]), (
        f"{doc}: the prose does not say there are {count} criteria"
    )
