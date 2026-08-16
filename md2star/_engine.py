"""Lazy accessor for md2star's resolved LLM/VLM engine descriptor.

md2star's three opt-in AI passes, the Markdown syntax lint, empty-alt-text
drafting, and diagram/figure reconstruction, all route their model calls
through ``best_engine_ai_helper.llm.chat``. Which backend and model those calls
use is decided *once*, by the suite's brief -> engine contract:

* ``md2star/llm.brief.yaml`` (committed) describes, hardware-independently, what
  md2star asks of a local model.
* On first use :func:`best_engine_ai_helper.ensure` resolves that brief against
  THIS machine and writes the concrete pick to the gitignored
  ``md2star/llm.engine.yaml``; every later run just loads the engine file.

This module owns the single lazy cache of that descriptor so the resolution
happens at most once per process and never at import time, the first AI pass to
run triggers it, and a conversion that uses no AI pass never touches it. There is
no hard-coded model tag anywhere in the package; the tag lives only in the
resolved engine file.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import os
from typing import Any

import best_engine_ai_helper as beh

# The package directory holds both contract files (llm.brief.yaml committed,
# llm.engine.yaml gitignored) — this is the ``DIR`` handed to ``beh.ensure``.
_PKG_DIR = os.path.dirname(os.path.abspath(__file__))

# Process-wide cache of the resolved descriptor; populated on first call to
# :func:`engine`. ``None`` means "not resolved yet".
_ENGINE: dict[str, Any] | None = None


def engine() -> dict[str, Any]:
    """Return md2star's resolved LLM/VLM engine descriptor, resolving on first use.

    Thin cache over :func:`best_engine_ai_helper.ensure`: loads
    ``md2star/llm.engine.yaml`` (backend + per-kind model for this machine), or
    resolves it from the committed ``md2star/llm.brief.yaml`` on first use and
    writes it. Raises loudly (``RuntimeError``) if the brief is missing — a
    committed brief is mandatory. Nothing is computed at import time; the first
    AI pass to run triggers resolution.

    Returns
    -------
    dict
        The engine descriptor (``backend`` / ``base_url`` and per-kind model),
        as returned by :func:`best_engine_ai_helper.ensure`.
    """
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = beh.ensure(_PKG_DIR)
    return _ENGINE
