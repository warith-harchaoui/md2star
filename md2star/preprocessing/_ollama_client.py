"""Optional Ollama Python-client layer for the ``md2star[ai]`` extra.

The AI passes (:mod:`md2star.preprocessing.lint` and
:mod:`md2star.preprocessing.alt_text`) talk to a local Ollama daemon on
``localhost:11434``. Historically they did so with hand-rolled
:mod:`urllib.request` POSTs — zero Python dependencies, works everywhere.

Installing the ``md2star[ai]`` extra adds the official ``ollama`` Python
client, which this module wraps. When the client is importable, the two
public helpers here (:func:`list_model_names` and :func:`generate`) route
through it for the ergonomic, well-typed API; when it is *not* installed
they return ``None`` and each caller falls back to its inline urllib path,
so the v2.0 zero-dependency behaviour is preserved bit-for-bit.

The contract is deliberately narrow: both helpers are *best-effort* and
never raise — any client/network/daemon failure is swallowed into a
``None`` return, which every caller already treats as "degrade to the
untouched document". That keeps the AI passes strictly non-load-bearing
whether or not the extra is installed.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..logging import get_logger

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)

# Import the optional client once, at module load. ``OLLAMA`` is the module
# object when the ``[ai]`` extra is installed and ``None`` otherwise; callers
# branch on it to decide between the client path and their urllib fallback.
# A broad except (not just ImportError) guards against a half-installed or
# incompatible ``ollama`` build breaking import of the whole preprocessing
# package — the tool must still convert without the extra.
try:  # pragma: no cover - exercised via the injected fake in tests
    import ollama as _ollama

    OLLAMA: Any = _ollama
except Exception:  # noqa: BLE001 - any import failure means "extra absent"
    OLLAMA = None


def _names_from_list_response(resp: Any) -> list[str]:
    """Pull model tag strings out of an ``ollama.list()`` response.

    The client has returned both attribute-style objects (``resp.models`` of
    items with ``.model``) and plain dicts across versions, so probe both
    shapes defensively and keep only the non-empty names.
    """
    # Newer clients expose a typed ``ListResponse`` with ``.models``; older
    # ones (and the raw API) hand back a ``{"models": [...]}`` dict.
    models = getattr(resp, "models", None)
    if models is None:
        models = resp.get("models", []) if isinstance(resp, dict) else []

    names: list[str] = []
    for m in models or []:
        # Typed item → ``.model``; dict item → ``model`` (or legacy ``name``).
        name = getattr(m, "model", None)
        if name is None and isinstance(m, dict):
            name = m.get("model") or m.get("name")
        if name:
            names.append(name)
    return names


def list_model_names(timeout: float = 2.0) -> list[str] | None:
    """Return locally-pulled model tags via the client, or ``None``.

    ``None`` means "no client available, or the daemon was unreachable" —
    both cases the caller handles by falling back to its urllib probe (extra
    absent) or by treating the model as not-yet-pulled (daemon down).
    """
    # No extra installed → signal the caller to use its urllib fallback.
    if OLLAMA is None:
        return None
    try:
        # A per-call client lets us honour the caller's short timeout instead
        # of the module default, keeping the reachability probe snappy.
        client = OLLAMA.Client(timeout=timeout)
        return _names_from_list_response(client.list())
    except Exception as exc:  # noqa: BLE001 - best-effort probe, never fatal
        # Daemon down / socket error / unexpected payload → "no models".
        logger.debug("ollama client list() failed: %s", exc)
        return None


def generate(
    model: str,
    prompt: str,
    *,
    images: Sequence[str] | None = None,
    options: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> str | None:
    """Run a one-shot completion through the client; ``None`` on any failure.

    Parameters mirror the fields the urllib fallbacks post to
    ``/api/generate``: *model* tag, *prompt* text, optional *images* (file
    paths — the client reads and base64-encodes them), and Ollama *options*
    such as ``{"temperature": 0.0}``. A ``None`` return tells the caller to
    keep the original document untouched.
    """
    # No extra installed → let the caller take its urllib path instead.
    if OLLAMA is None:
        return None
    try:
        client = OLLAMA.Client(timeout=timeout)
        # ``stream=False`` yields one complete response object; passing image
        # *paths* lets the client own the base64 encoding the urllib path did
        # by hand. ``options or {}`` avoids sending a null options field.
        resp = client.generate(
            model=model,
            prompt=prompt,
            images=list(images) if images else None,
            options=options or {},
            stream=False,
        )
    except Exception as exc:  # noqa: BLE001 - network/model errors are non-fatal
        logger.debug("ollama client generate() failed: %s", exc)
        return None

    # Typed ``GenerateResponse`` exposes ``.response``; a dict payload uses the
    # same key. Strip and normalise empty output to ``None`` so callers apply
    # their "keep original" guard uniformly across both transports.
    text = getattr(resp, "response", None)
    if text is None and isinstance(resp, dict):
        text = resp.get("response")
    text = (text or "").strip()
    return text or None
