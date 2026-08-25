"""Opt-in LLM-powered Markdown syntax linter.

Resolution policy (off by default):

* No flag, or ``--no-lint``     → skip the lint entirely.
* ``--lint``                    → run the lint through the local model chosen by
                                  the suite's brief -> engine contract.
* Any failure (engine can't be resolved, daemon/model unreachable, suspicious
  output) → the original Markdown is returned unchanged so the overall
  conversion still succeeds.

The opt-in default keeps conversions deterministic and side-effect-free.
Pass ``--lint`` explicitly when you want the LLM to fix obvious syntax
issues (broken image links, unclosed code fences, malformed table pipes)
before Pandoc parses the file.

When enabled, :func:`lint_with_llm` sends the document to the model via
:func:`best_engine_ai_helper.llm.chat` (``kind="llm"``, temperature 0) and keeps
the response only if it passes a coarse length-sanity check (0.5×–2× of the
original). Any failure (transport error, suspicious output) falls back to the
original content unchanged, the lint is never load-bearing for a successful
conversion.

The backend and model come entirely from the resolved engine descriptor
(:mod:`md2star._engine`): md2star commits ``llm.brief.yaml`` and never hard-codes
a model tag. The transport owns the daemon/serving lifecycle, so this pass no
longer manages ``ollama serve`` / ``ollama pull`` itself.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

from best_engine_ai_helper import llm

from .._engine import engine
from ..logging import get_logger

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)


# The prompt is deliberately strict and repetitive: an LLM's instinct is to
# "improve" prose, but this pass must ONLY repair syntax. The explicit NEVER
# rules + the length guard in lint_with_llm are two independent defences
# against the model silently rewriting the user's words.
_LINT_PROMPT = """\
You are a Markdown syntax fixer. You receive raw Markdown and must return
ONLY the fixed Markdown — nothing else (no explanations, no code fences).

Rules:
1. Fix ONLY Markdown formatting/syntax errors:
   - Broken image links: `![alt(file.png)` → `![alt](file.png)`
   - Unclosed code fences: add missing closing ```
   - Malformed table pipes: `| col1 | col2` → `| col1 | col2 |`
   - Missing blank lines before headings or lists
   - Broken bold/italic: `**bold*` → `**bold**`
2. NEVER change any words, meaning, or content
3. NEVER add, remove, or rewrite sentences
4. NEVER change URLs, file paths, or citation keys
5. NEVER wrap your output in a code block
6. If the Markdown is already correct, return it unchanged
7. Preserve ALL existing whitespace patterns (indentation, blank lines)
   except where fixing requires adding a blank line

Return ONLY the fixed Markdown, character for character where no fix is needed."""


def lint_with_llm(content: str, model: str | None = None) -> str:
    """Send *content* to the local LLM for syntax-only fixes; return original on any failure.

    The 0.5×–2× length guard is a coarse hallucination/truncation check; if
    the response strays outside that band, the original is kept. Resolution of
    *which* model and backend to use is delegated entirely to the suite's
    brief -> engine contract (:func:`md2star._engine.engine`); *model* is an
    optional per-call tag override passed straight through to
    :func:`best_engine_ai_helper.llm.chat`. Any failure — the engine cannot be
    resolved (missing brief, no reachable backend/model), the request errors, or
    the output looks wrong — degrades to the untouched content.
    """
    try:
        # temperature=0.0 for a deterministic, minimal syntax fix — we want a
        # corrector, not a creative rewriter. The prompt precedes the document.
        prompt = _LINT_PROMPT + "\n\n" + content
        fixed = llm.chat(
            prompt,
            engine=engine(),
            kind="llm",
            temperature=0.0,
            model=model,
        )
    except Exception as e:  # noqa: BLE001 — any failure is non-fatal; keep original
        # Engine resolution, transport, or model errors all fall back to the
        # untouched document — the lint is never load-bearing.
        logger.warning(f"md2star warning: LLM lint failed: {e}")
        return content

    # A text prompt with no json_schema returns a str; normalise/guard anyway.
    fixed = (fixed or "").strip() if isinstance(fixed, str) else ""
    # Empty response → nothing to apply, keep the original.
    if not fixed:
        return content

    # Coarse hallucination/truncation guard: a wildly different length means we
    # distrust the model and keep the original untouched.
    original_len = len(content.strip())
    fixed_len = len(fixed)
    if fixed_len < original_len * 0.5 or fixed_len > original_len * 2.0:
        logger.warning("md2star warning: LLM lint output size too different, skipping")
        return content

    # Passed the length sanity check → accept the model's corrected markdown.
    return fixed
