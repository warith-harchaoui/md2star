"""LaTeX math handling for the intermediate Markdown.

Authors often wrap an inline LaTeX formula in backticks — either by reflex
(``\\`$x^2$\\```) or because they want to mix prose-style identifiers with
math (``\\`quality_threshold $\\in [0,1]$\\```). Pandoc treats backtick
content as a verbatim code span, so the math is rendered as monospace
literal text instead of as math.

This module rewrites those code spans into proper Pandoc math:

* A code span whose content is purely math is unwrapped: ``\\`$x^2$\\``` →
  ``$x^2$``.
* A code span that mixes plain text and math is merged into a single math
  expression: ``\\`quality_threshold $\\in [0,1]$\\``` →
  ``$\\text{quality threshold} \\in [0,1]$``. Underscores in the text
  portion are read as snake_case word separators and become spaces, since a
  literal ``_`` would mean subscript inside the resulting math context.

A code span with no math (just code/identifiers) is left untouched.

The module also exposes :data:`MATH_FORMULA_RE` so other passes (e.g. the
pipe-table soft-break inserter) can tokenize around math chunks and avoid
mutating them.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import re

# Pandoc-supported inline math delimiters. Order matters: the longer
# ``$$..$$`` and ``\\[..\\]`` display-math forms must be tried before the
# shorter ``$..$`` / ``\\(..\\)`` inline forms so the longer pair wins.
MATH_FORMULA_RE = re.compile(
    r"\$\$[^$\n]+?\$\$"
    r"|\$[^$\n]+?\$"
    r"|\\\([^)\n]+?\\\)"
    r"|\\\[[^\]\n]+?\\\]"
)


# Same alternations as MATH_FORMULA_RE, but wrapped in a single capture
# group so ``re.split`` keeps the math chunks as odd-indexed elements.
_MATH_SPLIT_RE = re.compile(rf"({MATH_FORMULA_RE.pattern})")


# An inline backtick code span: a single ``\\``…\\``` run that does not
# straddle newlines and is non-empty.
_CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")


def _strip_math_delims(chunk: str) -> str:
    """Return the content of a math chunk with its delimiters removed."""
    # Check the 2-char display delimiters ($$, \[) before the 1-char inline
    # ones so ``$$x$$`` strips both dollars, not just the outer pair.
    if chunk.startswith("$$") and chunk.endswith("$$"):
        return chunk[2:-2].strip()
    if chunk.startswith("$") and chunk.endswith("$"):
        return chunk[1:-1].strip()
    if chunk.startswith("\\(") and chunk.endswith("\\)"):
        return chunk[2:-2].strip()
    if chunk.startswith("\\[") and chunk.endswith("\\]"):
        return chunk[2:-2].strip()
    return chunk


def _wants_display_math(math_chunks: list[str]) -> bool:
    """True if any chunk uses display delimiters (``$$..$$`` or ``\\[..\\]``)."""
    return any(c.startswith("$$") or c.startswith("\\[") for c in math_chunks)


def _textify(raw: str) -> str:
    """Render a plain-text chunk for inclusion inside a math expression.

    Snake_case identifiers read more naturally as space-separated words, and
    a bare ``_`` inside a math context is parsed by LaTeX as a subscript
    operator. Replacing runs of underscores with a single space handles both
    issues at once.
    """
    text = raw.strip()
    if not text:
        return ""
    text = re.sub(r"_+", " ", text)
    return rf"\text{{{text}}}"


def _merge_code_span(content: str) -> str | None:
    """Merge text + math inside a code span into one math expression.

    Returns ``None`` when *content* contains no math chunk at all — the
    caller should leave the original code span untouched in that case.

    When the content is a single math chunk with no surrounding text the
    chunk is returned verbatim, preserving the user's original delimiter
    choice (``$..$``, ``\\(..\\)``, ``\\[..\\]``, ``$$..$$``). When the
    content mixes prose with math the result is unified under ``$..$`` (or
    ``$$..$$`` if any inner chunk was display-math), because the prose
    portion has to be folded in as ``\\text{}`` and can only live inside
    dollar-delimited math.
    """
    parts = _MATH_SPLIT_RE.split(content)
    if len(parts) < 3:
        return None  # no math match → not our concern

    # Even indices are plain text, odd indices are matched math chunks.
    has_prose = any(parts[i].strip() for i in range(0, len(parts), 2))
    math_chunks = [parts[i] for i in range(1, len(parts), 2)]

    # Pure math, no prose → return the chunk as-is so the original
    # delimiter style survives.
    if not has_prose and len(math_chunks) == 1:
        return math_chunks[0]

    delim = "$$" if _wants_display_math(math_chunks) else "$"

    # Walk the split parts in order, re-emitting each into the unified math
    # expression: even parts are prose (wrapped in \text{}), odd parts are the
    # inner math (delimiters stripped, since the whole thing gets re-wrapped).
    pieces: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            rendered = _textify(part)
            # Skip empty text fragments (e.g. between adjacent math chunks).
            if rendered:
                pieces.append(rendered)
        else:
            inner = _strip_math_delims(part)
            if inner:
                pieces.append(inner)

    # Everything collapsed to nothing → signal "leave the span alone".
    if not pieces:
        return None
    return f"{delim}{' '.join(pieces)}{delim}"


def unwrap_math_in_code_spans(text: str) -> str:
    """Rewrite backtick code spans whose content contains LaTeX math.

    Pure-math spans are unwrapped; mixed text/math spans are merged into a
    single math expression with text portions wrapped in ``\\text{}``.
    Code spans with no math are returned verbatim.
    """
    def _replace(match: re.Match) -> str:
        """Rewrite one matched code span, or leave it verbatim if it has no math.

        Parameters
        ----------
        match : re.Match
            A match of :data:`_CODE_SPAN_RE`; group 1 is the span's inner text.

        Returns
        -------
        str
            The merged math expression, or the original span (``match.group(0)``)
            when the content holds no LaTeX math.
        """
        merged = _merge_code_span(match.group(1))
        return merged if merged is not None else match.group(0)

    return _CODE_SPAN_RE.sub(_replace, text)
