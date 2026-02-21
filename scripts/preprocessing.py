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

import os
import re
import sys
import tempfile


def preprocess_markdown(content: str) -> str:
    """
    Ensure every list item in *content* is preceded by a blank line.

    Parameters
    ----------
    content : str
        Raw Markdown text (may contain fenced code blocks, headings,
        paragraphs, and list items).

    Returns
    -------
    str
        Transformed Markdown text with blank lines inserted before each
        list item that was not already preceded by one.

    Notes
    -----
    * Fenced code blocks (delimited by triple backticks) are left untouched
      so that code examples containing list-like syntax are not altered.
    * Both unordered (``-``, ``*``, ``+``) and ordered (``1.``, ``2.``, …)
      list items are detected.

    Examples
    --------
    >>> preprocess_markdown("Hello\\n- item1\\n- item2")
    'Hello\\n\\n- item1\\n\\n- item2'

    Code blocks are preserved as-is:

    >>> preprocess_markdown("```\\n- not a list\\n```")
    '```\\n- not a list\\n```'
    """
    lines: list[str] = content.split("\n")
    out_lines: list[str] = []

    # Track whether we are inside a fenced code block (``` … ```)
    in_code_block: bool = False

    # Regex matching a list item:
    #   optional leading whitespace  →  (\s*)
    #   list marker (-, *, +, or digit(s) followed by .)  →  (?:[-*+]|\d+\.)
    #   at least one space after the marker  →  \s+
    list_pattern: re.Pattern[str] = re.compile(
        r"^(\s*(?:[-*+]|\d+\.)\s+.*)"
    )

    for line in lines:
        # ── Toggle code-block state on fence delimiters ──
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            out_lines.append(line)
            continue

        # ── Skip processing inside code blocks ──
        if in_code_block:
            out_lines.append(line)
            continue

        # ── Inject a blank line before a list item if one is missing ──
        match = list_pattern.match(line)
        if match:
            if out_lines and out_lines[-1].strip() != "":
                out_lines.append("")

        out_lines.append(line)

    return "\n".join(out_lines)


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

    processed: str = preprocess_markdown(content)

    # Write to a temp file **in the same directory** as the input so that
    # relative paths (images, includes, …) keep resolving correctly.
    dir_name: str = os.path.dirname(os.path.abspath(in_path))
    fd, temp_path = tempfile.mkstemp(
        dir=dir_name, suffix=".md", prefix=".preprocessed_"
    )

    with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
        temp_file.write(processed)

    # Print the temp-file path so the calling shell script knows where it is.
    print(temp_path)
