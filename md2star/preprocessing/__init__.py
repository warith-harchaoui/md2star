"""md2star Markdown preprocessor package.

The orchestrator :func:`preprocess_markdown` runs a fixed sequence of phases
on a raw Markdown string before it reaches Pandoc. Each phase lives in its
own submodule so the pipeline is easy to test, extend, or swap.

Public API
----------
- :func:`preprocess_markdown`  — the orchestrator (only thing wrappers call)
- :func:`render_mermaid_local` — re-exported for tests/mocks
- :data:`PHASES`               — canonical phase-name set (for ``--skip-phase``)


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from .alt_text import DEFAULT_ALT_TEXT_MODEL, fill_empty_alt_text
from .lint import DEFAULT_LINT_MODEL, is_ollama_installed
from .mermaid import render_mermaid_local
from .pipeline import PHASES, isolate_images_for_pptx, preprocess_markdown

__all__ = [
    "preprocess_markdown",
    "isolate_images_for_pptx",
    "render_mermaid_local",
    "fill_empty_alt_text",
    "is_ollama_installed",
    "DEFAULT_LINT_MODEL",
    "DEFAULT_ALT_TEXT_MODEL",
    "PHASES",
]
