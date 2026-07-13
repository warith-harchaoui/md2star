"""HTML ``<table>`` → Pandoc pipe-table conversion.

Pandoc's DOCX writer silently drops raw HTML in the document body, so any
``<table>`` left in the Markdown after preprocessing would simply vanish.
This module parses HTML tables with a minimal :class:`HTMLParser` subclass
and emits an equivalent pipe-table that Pandoc renders natively.

Inline formatting tags inside cells (``<code>``, ``<strong>``, ``<em>``, …)
are translated to their Markdown equivalents so the formatting survives.
Local images embedded in cells are routed through
:func:`resize_image_for_cell` to prevent overflow.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

from .images import _CELL_IMG_RE, resize_image_for_cell
from .math import MATH_FORMULA_RE
from .regexes import PIPE_TABLE_ROW_RE

# HTML inline tag → (open_marker, close_marker) Markdown equivalents.
_INLINE_TAGS: dict[str, tuple[str, str]] = {
    "code": ("`", "`"),
    "strong": ("**", "**"),
    "b": ("**", "**"),
    "em": ("*", "*"),
    "i": ("*", "*"),
    "s": ("~~", "~~"),
    "del": ("~~", "~~"),
}


class _TableParser(HTMLParser):
    """Streaming HTML parser that collects rows of Markdown cell strings.

    Inline tags push/pop their Markdown markers onto a stack so nesting is
    preserved across cells; ``<img>`` tags inside cells emit
    ``![alt](src)`` Markdown directly.
    """

    def __init__(self) -> None:
        super().__init__()
        # Accumulated output: completed rows of already-rendered cell strings,
        # plus the indices of rows that came from <th>/<thead> (header rows).
        self.rows: list[list[str]] = []
        self.header_rows: set[int] = set()
        # Streaming cursors — the row/cell currently being built (None between
        # elements) and a flag for "are we inside a cell right now?".
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None
        self._in_cell: bool = False
        # Open inline markers (``**``, `` ` ``…) awaiting their close tag, so
        # nested formatting is emitted in the right order.
        self._inline_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:  # noqa: ARG002
        tag = tag.lower()
        if tag == "tr":
            self._current_row = []
        elif tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = []
            if tag == "th" and self._current_row is not None:
                self.header_rows.add(len(self.rows))
        elif self._in_cell and tag in _INLINE_TAGS:
            open_marker, _ = _INLINE_TAGS[tag]
            if self._current_cell is not None:
                self._current_cell.append(open_marker)
            self._inline_stack.append(tag)
        elif self._in_cell and tag == "img":
            attr_dict = dict(attrs)
            src = attr_dict.get("src", "")
            alt = attr_dict.get("alt", "")
            if src and self._current_cell is not None:
                self._current_cell.append(f"![{alt}]({src})")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in ("td", "th"):
            if self._current_row is not None and self._current_cell is not None:
                self._current_row.append("".join(self._current_cell).strip())
            self._current_cell = None
            self._in_cell = False
            self._inline_stack.clear()
        elif tag == "tr":
            if self._current_row is not None:
                self.rows.append(self._current_row)
            self._current_row = None
        elif self._in_cell and tag in _INLINE_TAGS:
            _, close_marker = _INLINE_TAGS[tag]
            if self._current_cell is not None:
                self._current_cell.append(close_marker)
            if self._inline_stack and self._inline_stack[-1] == tag:
                self._inline_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_cell and self._current_cell is not None:
            self._current_cell.append(html.unescape(data))


def html_table_to_markdown(table_html: str, base_dir: str = ".") -> str:
    """Convert a single ``<table>...</table>`` block to a pipe-table string.

    Returns the original *table_html* on parse failure or empty rows.
    """
    parser = _TableParser()
    try:
        parser.feed(table_html)
    except Exception:
        return table_html

    rows = parser.rows
    if not rows:
        return table_html

    def _fix_cell_images(cell: str) -> str:
        def _resize(m: re.Match) -> str:
            alt = m.group(1)
            src = m.group(2)
            resized = resize_image_for_cell(src, base_dir)
            return f"![{alt}]({resized})"
        return _CELL_IMG_RE.sub(_resize, cell)

    rows = [[_fix_cell_images(c) for c in row] for row in rows]

    col_count = max(len(r) for r in rows)
    col_widths = [1] * col_count
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))

    def _format_row(cells: list[str]) -> str:
        padded = [
            cells[i].ljust(col_widths[i]) if i < len(cells) else " " * col_widths[i]
            for i in range(col_count)
        ]
        return "| " + " | ".join(padded) + " |"

    def _separator() -> str:
        return "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"

    md_lines: list[str] = []
    md_lines.append(_format_row(rows[0]))
    md_lines.append(_separator())
    for row in rows[1:]:
        md_lines.append(_format_row(row))

    return "\n".join(md_lines)


# Complete <table>…</table> block (case-insensitive, multi-line, non-greedy).
_TABLE_RE = re.compile(
    r"(<table(?:[^>]*)>.*?</table>)",
    re.IGNORECASE | re.DOTALL,
)


def convert_html_tables(content: str, base_dir: str = ".") -> str:
    """Replace every ``<table>`` block in *content* with a pipe-table equivalent."""
    def _replace(match: re.Match) -> str:
        return "\n\n" + html_table_to_markdown(match.group(1), base_dir) + "\n\n"

    return _TABLE_RE.sub(_replace, content)


# ---------------------------------------------------------------------------
# Pipe-table separator normalization (column-width hints + trailing blank line)
# ---------------------------------------------------------------------------
#
# Pandoc's DOCX/PPTX writer uses the *width of the dashes* in a pipe-table's
# header separator as a per-column width hint — but ONLY when the total dash
# count exceeds the ``--columns`` setting (default 72). A uniform separator
# like ``|---|---|---|`` (9 dashes) is below that threshold, so Pandoc ignores
# it and auto-fits each column to its longest cell. For skewed tables (e.g. a
# 4 / 141 / 7-character ratio) that produces a cramped middle column and lots
# of wasted page width.
#
# :func:`normalize_pipe_tables` rewrites every pipe-table separator with dashes
# proportional to the max cell length in each column, scaled so the total
# exceeds ``min_total`` (default 90 > 72). Alignment markers (``:---``,
# ``:---:``, ``---:``) are preserved. A blank line is enforced after every
# table block so Pandoc cleanly terminates the table.


_SEP_CELL_RE = re.compile(r"^(:?)-+(:?)$")

# Unicode zero-width space — invisible character that DOCX/PPTX renderers treat
# as a soft-break opportunity. Inserted after path/identifier separators inside
# long unbreakable runs so cells with file paths, snake_case identifiers, or
# slash-delimited URLs can wrap at sensible points instead of one character at
# a time. If the column is wide enough no wrap occurs, so this is harmless.
_ZWSP = "​"

# A non-whitespace run inside a cell. Used to find unbreakable substrings that
# need soft-break insertion.
_LONG_RUN_RE = re.compile(r"\S+")


_PROTECTED_RE = re.compile(rf"(`[^`\n]*`|{MATH_FORMULA_RE.pattern})")


def _insert_soft_breaks(cell: str, min_run_len: int = 25) -> str:
    """Insert zero-width spaces inside long unbreakable runs in *cell*.

    Only runs of at least ``min_run_len`` characters get processed, and only
    when they contain a path/identifier separator (``/`` or ``_``). Content
    inside backtick-delimited code spans **and** inside LaTeX math chunks
    (``$..$``, ``$$..$$``, ``\\(..\\)``, ``\\[..\\]``) is preserved verbatim
    — a ZWSP injected mid-formula would break LaTeX rendering, and a ZWSP
    inside a code span would break the literal text.
    """
    if len(cell) < min_run_len:
        return cell

    # Tokenize so we leave code spans and math alone. Even-indexed pieces are
    # normal text; odd-indexed pieces are protected (incl. their delimiters).
    parts = _PROTECTED_RE.split(cell)
    for idx in range(0, len(parts), 2):
        chunk = parts[idx]
        if not chunk:
            continue

        def _rewrite(match: re.Match) -> str:
            word = match.group(0)
            if len(word) < min_run_len or not re.search(r"[/_]", word):
                return word
            return word.replace("/", "/" + _ZWSP).replace("_", "_" + _ZWSP)

        parts[idx] = _LONG_RUN_RE.sub(_rewrite, chunk)
    return "".join(parts)


# Sentence/clause boundaries (in priority order) used to split long cells
# into multiple lines via ``<br/>``. We prefer hard sentence ends; fall back
# to semicolons; fall back to commas as a last resort.
_BREAK_RULES = (
    re.compile(r"(\.\s+)"),
    re.compile(r"(;\s+)"),
    re.compile(r"(,\s+)"),
)


def _wrap_long_cell(
    cell: str,
    max_total: int = 120,
    target_line_len: int = 80,
) -> str:
    """Insert ``<br/>`` inside a long cell so its longest line stays short.

    A cell whose plain length exceeds *max_total* is split at sentence /
    semicolon / comma boundaries; the function picks the coarsest rule that
    produces lines ≤ *target_line_len*. Cells inside code spans are passed
    through unchanged so backtick formatting survives. ``<br/>`` is the only
    in-cell line break Pandoc's pipe-table parser honours.
    """
    if len(cell) < max_total or "<br" in cell.lower():
        return cell

    # Skip cells that are mostly code or math — we don't want to break inside
    # a backtick span or split a formula on its inner ``, `` or ``. ``.
    protected_chars = sum(
        len(m.group(0))
        for m in re.finditer(rf"`[^`\n]+`|{MATH_FORMULA_RE.pattern}", cell)
    )
    if protected_chars > len(cell) * 0.7:
        return cell

    for splitter in _BREAK_RULES:
        pieces = splitter.split(cell)
        if len(pieces) <= 1:
            continue
        # Recombine pieces, inserting <br/> when adding the next chunk would
        # push the current line past target_line_len.
        out: list[str] = []
        line_len = 0
        for p in pieces:
            if not p:
                continue
            if line_len + len(p) > target_line_len and out:
                # Move the trailing whitespace from the prior segment onto the
                # break so the visible cell content stays clean.
                tail = out[-1]
                stripped = tail.rstrip()
                trailing_ws = tail[len(stripped):]
                out[-1] = stripped + trailing_ws.rstrip(" ")
                out.append("<br/>")
                line_len = 0
            out.append(p)
            line_len += len(p)
        wrapped = "".join(out)
        # Accept this split only if no resulting line is still too long.
        longest = max(
            (len(seg) for seg in re.split(r"<br\s*/?>", wrapped)),
            default=0,
        )
        if longest <= target_line_len:
            return wrapped
    # No rule produced short enough lines: leave the cell alone rather than
    # forcing an ugly mid-word break.
    return cell


def _cell_longest_line(cell: str) -> int:
    """Return the length of the longest ``<br/>``-delimited line in *cell*.

    Used as the per-column weight for the proportional separator: the column
    only needs to be wide enough for its longest visual line, not for the
    total length of its biggest cell.
    """
    if not cell:
        return 0
    lines = re.split(r"<br\s*/?>", cell)
    return max(len(ln) for ln in lines)


def _column_is_single_word(rows: list[list[str]], col_idx: int) -> bool:
    """True iff every non-empty cell in column ``col_idx`` is a single word.

    A "single-word" cell has no whitespace inside the visible text, so it
    cannot wrap onto a second line — DOCX/PPTX renderers will instead break
    it character-by-character if the column is too narrow. To prevent that
    ugly look, the caller widens such columns by a small multiplicative
    slack factor. Empty cells are ignored (they don't fight for space), but
    a column where every cell is empty returns False so we don't accidentally
    inflate a no-content column.
    """
    has_content = False
    for row in rows:
        cell = row[col_idx].strip() if col_idx < len(row) else ""
        if not cell:
            continue
        has_content = True
        # Strip ``<br/>`` so a wrapped two-line cell still has its space.
        flat = re.sub(r"<br\s*/?>", " ", cell)
        if len(flat.split()) > 1:
            return False
    return has_content


def _split_row(line: str) -> list[str]:
    """Split a pipe-table row into trimmed cell strings, ignoring outer pipes."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _parse_separator(line: str) -> list[str] | None:
    """Return alignment markers per column, or None if *line* is not a separator.

    Alignment markers: '' (default), 'l' (``:---``), 'r' (``---:``), 'c'
    (``:---:``). All cells must be valid for the row to be classified as a
    separator.
    """
    stripped = line.strip()
    if not stripped.startswith("|") and "|" not in stripped:
        return None
    cells = _split_row(line)
    if not cells:
        return None
    aligns: list[str] = []
    for c in cells:
        m = _SEP_CELL_RE.match(c)
        if not m:
            return None
        left, right = m.group(1), m.group(2)
        if left and right:
            aligns.append("c")
        elif right:
            aligns.append("r")
        elif left:
            aligns.append("l")
        else:
            aligns.append("")
    return aligns


def _build_separator(widths: list[int], aligns: list[str]) -> str:
    """Render a pipe-table separator row from per-column dash counts + alignments."""
    cells: list[str] = []
    # strict=False — widths and aligns can have different lengths in
    # malformed input; we'd rather build a separator from the shorter
    # of the two than raise.
    for w, a in zip(widths, aligns, strict=False):
        w = max(3, w)  # Pandoc requires at least 3 dashes per column
        if a == "c":
            cells.append(":" + "-" * (w - 2) + ":")
        elif a == "l":
            cells.append(":" + "-" * (w - 1))
        elif a == "r":
            cells.append("-" * (w - 1) + ":")
        else:
            cells.append("-" * w)
    return "|" + "|".join(cells) + "|"


def normalize_pipe_tables(
    content: str,
    min_total: int = 90,
    min_per_col: int = 3,
    min_weight_per_col: int = 15,
    single_word_slack: float = 1.7,
) -> str:
    """Rewrite pipe-table separators with proportional dashes; ensure trailing blank line.

    Columns whose cells are *all* single-word (no internal whitespace) are
    given a ``single_word_slack`` multiplicative bump on their weight, since
    such cells cannot wrap and would otherwise get squeezed character-by-
    character against multi-word columns that can break across lines.

    The transformation is idempotent: running it twice yields the same output.
    Tables inside fenced code blocks are left untouched.
    """
    lines = content.split("\n")
    out: list[str] = []
    in_code = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code
            out.append(line)
            i += 1
            continue

        if in_code or not PIPE_TABLE_ROW_RE.match(line):
            out.append(line)
            i += 1
            continue

        # Candidate header row; row i+1 must be a separator.
        if i + 1 >= len(lines):
            out.append(line)
            i += 1
            continue

        aligns = _parse_separator(lines[i + 1])
        if aligns is None:
            out.append(line)
            i += 1
            continue

        # Collect the full table block.
        block_end = i + 2
        while block_end < len(lines) and PIPE_TABLE_ROW_RE.match(lines[block_end]):
            block_end += 1

        header = _split_row(lines[i])
        body = [_split_row(lines[k]) for k in range(i + 2, block_end)]
        ncols = max(len(header), len(aligns), *(len(r) for r in body), 1)

        def _pad(row: list[str]) -> list[str]:
            # Defined fresh each iteration and used immediately below
            # (`all_rows = [_pad(header)] + [_pad(r) for r in body]`);
            # the loop-variable late-binding pattern ruff B023 warns
            # about is harmless here. We don't keep _pad past this
            # iteration, and `ncols` has its current value at call time.
            return row + [""] * (ncols - len(row))

        # Pre-wrap long cells so a single 200-char description doesn't force
        # its column to claim almost all of the page width and squeeze the
        # other columns down to one character per line. The wrap inserts
        # ``<br/>`` at clause boundaries so the longest *visible line* per
        # cell stays manageable.
        body = [[_wrap_long_cell(c) for c in row] for row in body]
        header = [_wrap_long_cell(c) for c in header]
        all_rows = [_pad(header)] + [_pad(r) for r in body]

        # ``col_weight`` is the *ratio* driver. We base it on the longest
        # ``<br/>``-delimited line in any cell of the column (so post-wrap
        # cells contribute their longest *line*, not their total length) and
        # floor it at ``min_weight_per_col`` so a 4-char label column doesn't
        # collapse to 3 % of the page width next to a 200-char description.
        # Columns where every populated cell is a single word also get a
        # ``single_word_slack`` bump so unbreakable tokens have breathing room.
        col_weight: list[int] = []
        for c in range(ncols):
            base = max(_cell_longest_line(row[c]) for row in all_rows)
            # Apply the floor *before* the single-word bump so a 4-char label
            # column (floored to ``min_weight_per_col``) still gets the
            # multiplicative slack on its already-padded weight — otherwise
            # the floor would silently swallow the bonus.
            base = max(min_weight_per_col, base)
            if _column_is_single_word(all_rows, c):
                base = int(round(base * single_word_slack))
            col_weight.append(base)
        total = sum(col_weight)
        if total < min_total:
            scale = min_total / total
            widths = [max(min_per_col, int(round(w * scale))) for w in col_weight]
        else:
            widths = col_weight

        aligns = (aligns + [""] * ncols)[:ncols]
        new_sep = _build_separator(widths, aligns)

        # Soft-break long unbreakable strings (file paths, snake_case ids) in
        # every cell so narrow columns don't fall back to character-per-line.
        def _emit_row(cells: list[str]) -> str:
            return "| " + " | ".join(_insert_soft_breaks(c) for c in cells) + " |"

        out.append(_emit_row(header))
        out.append(new_sep)
        for row in body:
            out.append(_emit_row(row))

        # Ensure a blank line terminates the table block.
        if block_end >= len(lines) or lines[block_end].strip() != "":
            out.append("")

        i = block_end

    return "\n".join(out)
