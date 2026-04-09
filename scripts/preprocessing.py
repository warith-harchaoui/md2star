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
import os
import re
import sys
import tempfile
import urllib.request
import zlib


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
    Also render Mermaid diagrams using an external API.

    Parameters
    ----------
    content : str
        Raw Markdown text (may contain fenced code blocks, headings,
        paragraphs, and list items).
    base_dir : str
        Directory to store the generated mermaid diagrams.

    Returns
    -------
    str
        Transformed Markdown text with blank lines inserted before each
        list item that was not already preceded by one, and Mermaid blocks
        converted to image links.

    Notes
    -----
    * Fenced code blocks (delimited by triple backticks) are left untouched
      (except for Mermaid blocks) so that code examples containing list-like 
      syntax are not altered.
    * Both unordered (``-``, ``*``, ``+``) and ordered (``1.``, ``2.``, …)
      list items are detected.
    """
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
