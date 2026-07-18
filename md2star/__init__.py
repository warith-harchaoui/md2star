"""md2star — Markdown → DOCX/PPTX/PDF bridge built on Pandoc.

Module summary
--------------
Public package surface for md2star. Re-exports the preprocessor entry
points so consumers can import them either from the top-level package
or from the ``md2star.preprocessing`` submodule.

Usage
-----
>>> from md2star import preprocess_markdown
>>> out = preprocess_markdown("# Hello\\n", base_dir=".")
>>> print(out.splitlines()[0])  # '# Hello'
# Hello

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)
"""

from __future__ import annotations

# Single source of truth for the package version. Hatchling reads this
# string at build time (see ``[tool.hatch.version]`` in pyproject.toml),
# so the wheel metadata, ``md2star --version``, the HTTP/MCP surfaces and
# the GUI banner can never drift apart again — bump it here and nowhere
# else. (v2.5.1/v2.5.2 drifted precisely because two copies existed.)
__version__: str = "2.6.0"

from .preprocessing import (
    DEFAULT_ALT_TEXT_MODEL,
    DEFAULT_LINT_MODEL,
    fill_empty_alt_text,
    is_ollama_installed,
    preprocess_markdown,
    render_mermaid_local,
)

__all__ = [
    "__version__",
    "preprocess_markdown",
    "render_mermaid_local",
    "fill_empty_alt_text",
    "is_ollama_installed",
    "DEFAULT_LINT_MODEL",
    "DEFAULT_ALT_TEXT_MODEL",
]
