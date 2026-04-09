#!/usr/bin/env python3
"""
preprocessing.py — Markdown pre-processor for md2star.

Applies transformations to the input Markdown **before** passing it to Pandoc.
Currently, this ensures that every list item is preceded by a blank line, which:

1. Fixes Markdown lists that are "glued" to the preceding paragraph (a common
   authoring habit that Pandoc sometimes renders as inline text instead of a
   proper list).
2. Converts *tight* lists into *loose* lists, resulting in better visual
   spacing in DOCX / PPTX output.
3. Automatically renders Mermaid code blocks as PNGs using Kroki to inject
   them successfully during layout.

The script writes the processed content to a temporary file (in the same
directory as the input so that relative image/link paths keep working) and
prints the path to stdout so the calling shell wrapper can feed it to Pandoc.

Usage
-----
Called automatically by the ``md2docx`` / ``md2pptx`` wrappers::

    TEMP_MD=$(python3 preprocessing.py input.md)
    pandoc "$TEMP_MD" …

Examples
--------
Direct CLI invocation for debugging::

    $ python3 scripts/preprocessing.py notes.md
    /path/to/.preprocessed_aBcD1234.md

Author
------
Warith Harchaoui
"""

from __future__ import annotations

import base64
import hashlib
import html
import os
import re
import sys
import tempfile
import urllib.request
import zlib
from html.parser import HTMLParser
from typing import Optional


# ───────────────────────────────────────────────────────────────────────────
# HTML table → Markdown pipe-table converter
# ───────────────────────────────────────────────────────────────────────────

class _TableParser(HTMLParser):
    """Minimal HTML parser that extracts rows and cells from an HTML table.

    Parameters
    ----------
    None (constructed via standard HTMLParser interface).

    Attributes
    ----------
    rows : list[list[str]]
        Collected rows, each being a list of cell text strings.
    header_rows : set[int]
        Indices of rows whose cells were originally ``<th>`` elements.
    """


# Map from HTML inline tag → (open_marker, close_marker) for Markdown
_INLINE_TAGS: dict[str, tuple[str, str]] = {
    "code": ("`", "`"),
    "strong": ("**", "**"),
    "b": ("**", "**"),
    "em": ("*", "*"),
    "i": ("*", "*"),
    "s": ("~~", "~~"),
    "del": ("~~", "~~"),
}

# Regex that finds Markdown image links inside a cell string so we can
# resize them.  Matches both bare ![]() and ![](){...} forms.
_CELL_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)(?:\{[^}]*\})?")


class _TableParser(HTMLParser):
    """HTML parser that converts an HTML table into a list of Markdown rows.

    Inline formatting tags (``<code>``, ``<strong>``, ``<em>``, etc.) are
    translated to their Markdown equivalents so that cell content is rendered
    correctly by Pandoc rather than passed through as raw HTML (which is
    silently ignored in DOCX output).

    Attributes
    ----------
    rows : list[list[str]]
        Each element is a row; each row is a list of cell Markdown strings.
    header_rows : set[int]
        Row indices whose cells originated from ``<th>`` elements.
    """

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.header_rows: set[int] = set()
        self._current_row: Optional[list[str]] = None
        # Each cell fragment is a string; inline markers are pushed/popped
        # as we enter/leave inline tags.
        self._current_cell: Optional[list[str]] = None
        self._in_cell: bool = False
        # Stack tracking which inline open-markers are open so we can close
        # them properly on the matching end tag.
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
            # Handle <img src="..." alt="..."> inside a cell
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



def resize_image_for_cell(
    src: str,
    base_dir: str,
    max_px: int = 400,
) -> str:
    """Resize a local image so it fits comfortably inside a table cell.

    When an image is embedded inside a Markdown pipe-table cell, the Pandoc
    ``{width=100%}`` attribute refers to the *full page width*, not the cell
    width.  The only reliable way to prevent cropping is to physically resize
    the image file to a small maximum dimension so it fits naturally.

    URL-based images are returned unchanged (network images are left for
    Pandoc to handle).

    Parameters
    ----------
    src : str
        Image path as it appears in the Markdown source (may be relative).
    base_dir : str
        Directory of the originating Markdown file, used to resolve relative
        paths.
    max_px : int
        Maximum width **and** height of the resized image in pixels.
        Defaults to ``400`` px, which comfortably fits most table cells.

    Returns
    -------
    str
        Absolute path to the (possibly resized) image file.
    """
    # Leave URL images alone
    if src.startswith(("http://", "https://", "//", "data:")):
        return src

    abs_src = src if os.path.isabs(src) else os.path.join(base_dir, src)
    abs_src = os.path.abspath(abs_src)

    if not os.path.exists(abs_src):
        return src  # can't resize what we can't find

    try:
        from PIL import Image  # type: ignore[import-untyped]

        img = Image.open(abs_src)
        w, h = img.size
        if w <= max_px and h <= max_px:
            return abs_src  # already small enough

        # Resize while preserving aspect ratio
        img.thumbnail((max_px, max_px), Image.LANCZOS)

        # Save the resized copy alongside the original
        stem, ext = os.path.splitext(abs_src)
        out_path = f"{stem}_cell{ext}"
        img.save(out_path)
        return out_path
    except Exception:
        return abs_src  # if Pillow fails, use original


def html_table_to_markdown(table_html: str, base_dir: str = ".") -> str:
    """Convert a raw HTML ``<table>`` block into a Pandoc pipe-table string.

    Pandoc's DOCX writer ignores raw HTML, so any ``<table>`` that survives
    into the document body will be silently dropped.  This function parses the
    HTML and emits an equivalent Markdown pipe-table that Pandoc can render
    natively.

    Inline HTML formatting tags (``<code>``, ``<strong>``, etc.) are converted
    to their Markdown equivalents.  Local images embedded in cells are resized
    via :func:`resize_image_for_cell` to prevent them from overflowing.

    Parameters
    ----------
    table_html : str
        Complete HTML string starting with ``<table`` and ending with
        ``</table>``.
    base_dir : str
        Directory of the source Markdown file, used to resolve relative image
        paths for resizing.  Defaults to the current directory.

    Returns
    -------
    str
        A Pandoc-compatible pipe-table Markdown string, or the original
        *table_html* if parsing fails or yields an empty table.
    """
    parser = _TableParser()
    try:
        parser.feed(table_html)
    except Exception:
        return table_html  # fall back to original on any parse error

    rows = parser.rows
    if not rows:
        return table_html

    # Resize any local images found in cells
    def _fix_cell_images(cell: str) -> str:
        def _resize(m: re.Match) -> str:
            alt = m.group(1)
            src = m.group(2)
            resized = resize_image_for_cell(src, base_dir)
            return f"![{alt}]({resized})"
        return _CELL_IMG_RE.sub(_resize, cell)

    rows = [[_fix_cell_images(c) for c in row] for row in rows]

    # Compute per-column widths for the separator row
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


# ---------------------------------------------------------------------------
# Regex that matches a complete <table>...</table> block (case-insensitive,
# spanning multiple lines, non-greedy so nested content does not bleed over).
# ---------------------------------------------------------------------------
_TABLE_RE = re.compile(
    r"(<table(?:[^>]*)>.*?</table>)",
    re.IGNORECASE | re.DOTALL,
)


def convert_html_tables(content: str, base_dir: str = ".") -> str:
    """Replace all HTML ``<table>`` blocks in *content* with Markdown tables.

    Parameters
    ----------
    content : str
        Full Markdown source that may contain one or more HTML ``<table>``
        blocks alongside regular Markdown.
    base_dir : str
        Directory of the source Markdown file, forwarded to
        :func:`html_table_to_markdown` for relative image path resolution.

    Returns
    -------
    str
        Source with every HTML table replaced by an equivalent Markdown
        pipe-table.  Non-table content is left unchanged.
    """
    def _replace(match: re.Match) -> str:
        return "\n\n" + html_table_to_markdown(match.group(1), base_dir) + "\n\n"

    return _TABLE_RE.sub(_replace, content)


# ───────────────────────────────────────────────────────────────────────────
# Image auto-width
# ───────────────────────────────────────────────────────────────────────────

# Matches a Markdown image that has NO trailing attribute block.
# Excludes images that already carry ``{...}`` attributes.
_IMAGE_NO_ATTR_RE = re.compile(
    r"(!\[[^\]]*\]\([^)]+\))(?!\s*\{)"
)


def fix_image_widths(content: str) -> str:
    """Append ``{width=100%}`` to every image that has no explicit attributes.

    This prevents images from overflowing the page or being cropped when Pandoc
    generates DOCX / PPTX output.  Images that already carry an attribute block
    (e.g. ``{width=80%}``) are left untouched.

    Parameters
    ----------
    content : str
        Full Markdown source.

    Returns
    -------
    str
        Source with ``{width=100%}`` appended to every undecorated image.
    """
    return _IMAGE_NO_ATTR_RE.sub(r"\1{width=100%}", content)


def fetch_kroki_mermaid(content: str, out_dir: str) -> str:
    """
    Send mermaid code to Kroki and download it as PNG.

    Images are cached natively based on the hash of their content 
    to avoid re-downloading identical graphs.

    Parameters
    ----------
    content : str
        Mermaid markup string representing a valid graph.
    out_dir : str
        Directory to save the produced image into.

    Returns
    -------
    str
        Absolute filepath to the resulting PNG.
    """
    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
    filename = f".mermaid_{content_hash}.png"
    filepath = os.path.join(os.path.abspath(out_dir), filename)

    if os.path.exists(filepath):
        return filepath

    compressed = zlib.compress(content.encode('utf-8'))
    b64 = base64.urlsafe_b64encode(compressed).decode('utf-8')
    url = f"https://kroki.io/mermaid/png/{b64}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; md2star/1.0)"}
    )
    with urllib.request.urlopen(req) as response, open(filepath, "wb") as f:
        f.write(response.read())

    return filepath


def preprocess_markdown(content: str, base_dir: str = ".") -> str:
    """
    Ensure every list item in *content* is preceded by a blank line.
    Also render Mermaid diagrams using an external API, convert HTML tables
    to native Markdown pipe-tables, and resize bare images to fit the page.

    Parameters
    ----------
    content : str
        Raw Markdown text (may contain fenced code blocks, headings,
        paragraphs, list items, HTML tables, and image links).
    base_dir : str
        Directory to store the generated mermaid diagrams.

    Returns
    -------
    str
        Transformed Markdown text where:

        * blank lines are inserted before each list item that lacked one;
        * Mermaid fenced blocks are replaced by locally-cached PNG image links;
        * HTML ``<table>`` blocks are converted to Pandoc pipe-tables;
        * bare image links (no explicit ``{...}`` attrs) get ``{width=100%}``
          so they scale to the page width without cropping.

    Notes
    -----
    * Fenced code blocks (delimited by triple backticks) are left untouched
      (except for Mermaid blocks) so that code examples containing list-like
      syntax are not altered.
    * Both unordered (``-``, ``*``, ``+``) and ordered (``1.``, ``2.``, …)
      list items are detected.
    """
    # ── Phase 0: HTML table conversion ──────────────────────────────────────
    # Must run before line-splitting so the full multi-line <table> blocks are
    # visible to the regex.
    content = convert_html_tables(content, base_dir)

    lines: list[str] = content.split("\n")

    out_lines: list[str] = []
    # Track whether we are inside a fenced code block (``` … ```)
    in_code_block: bool = False
    in_mermaid_block: bool = False
    mermaid_lines: list[str] = []

    # Regex matching a list item:
    #   optional leading whitespace  →  (\s*)
    #   list marker (-, *, +, or digit(s) followed by .)  →  (?:[-*+]|\d+\.)
    #   at least one space after the marker  →  \s+
    list_pattern: re.Pattern[str] = re.compile(
        r"^(\s*(?:[-*+]|\d+\.)\s+.*)"
    )

    for line in lines:
        stripped_line = line.strip()

        # ── Entering code-block ──
        if stripped_line.startswith("```") and not in_code_block:
            in_code_block = True
            # Mermaid blocks are parsed and skipped from final output initially.
            if stripped_line.lower().startswith("```mermaid"):
                in_mermaid_block = True
            else:
                out_lines.append(line)
            continue

        # ── Exiting code-block ──
        if stripped_line.startswith("```") and in_code_block:
            in_code_block = False
            if in_mermaid_block:
                in_mermaid_block = False
                mermaid_content = "\n".join(mermaid_lines)
                try:
                    img_name = fetch_kroki_mermaid(mermaid_content, base_dir)
                    if out_lines and out_lines[-1].strip() != "":
                        out_lines.append("")
                    out_lines.append(f"![]({img_name})\n")
                except Exception as e:
                    print(f"md2star warning: Kroki API rendering failed: {e}", file=sys.stderr)
                    # Fallback on failure
                    out_lines.append("```mermaid")
                    out_lines.extend(mermaid_lines)
                    out_lines.append("```")
                mermaid_lines = []
            else:
                out_lines.append(line)
            continue

        # ── Inside code-block ──
        if in_code_block:
            if in_mermaid_block:
                mermaid_lines.append(line)
            else:
                out_lines.append(line)
            continue

        # ── Inject a blank line before a list item if one is missing ──
        match = list_pattern.match(line)
        if match:
            if out_lines and out_lines[-1].strip() != "":
                out_lines.append("")

        out_lines.append(line)

    result = "\n".join(out_lines)

    # ── Phase 2: Image auto-width ────────────────────────────────────────────
    # Append {width=100%} to images that have no explicit attributes so they
    # always fit within the document/slide page area.
    result = fix_image_widths(result)

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 preprocessing.py <input.md>")
        sys.exit(1)

    in_path: str = sys.argv[1]

    # Read the original Markdown source
    with open(in_path, "r", encoding="utf-8") as f:
        content = f.read()

    dir_name: str = os.path.dirname(os.path.abspath(in_path))
    processed: str = preprocess_markdown(content, base_dir=dir_name)

    # Write to a temp file **in the same directory** as the input so that
    # relative paths (images, includes, …) keep resolving correctly.
    fd, temp_path = tempfile.mkstemp(
        dir=dir_name, suffix=".md", prefix=".preprocessed_"
    )

    with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
        temp_file.write(processed)

    # Print the temp-file path so the calling shell script knows where it is.
    print(temp_path)
