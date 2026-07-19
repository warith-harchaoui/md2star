"""Opt-in alt-text drafting for empty image alts via a local Ollama vision model.

Gated by the same ``--lint`` flag as :mod:`md2star.preprocessing.lint`:

* No flag, or ``--no-lint``         → skip the pass entirely.
* ``--lint`` + Ollama installed     → describe each ``![](src)`` whose alt is
                                      empty and whose ``src`` resolves to a
                                      readable local file; URLs / data URIs /
                                      missing files / non-empty alts pass
                                      through untouched.
* ``--lint`` + Ollama missing       → quiet skip (the lint pass already
                                      printed the install hint).

The vision model defaults to ``llama3.2-vision``; override with the
``MD2STAR_ALT_TEXT_MODEL`` env variable. The model is only auto-pulled when
the lint daemon was already spawned by :mod:`lint`, so a user who only wants
the text lint will not accidentally start a multi-gigabyte vision download.

The vision model defaults to whatever the text lint already uses
(``gemma4:e2b-mlx`` on macOS, ``gemma4:e2b`` elsewhere) — the gemma4
family is multimodal, so one model pull powers both passes. Override
with the ``MD2STAR_ALT_TEXT_MODEL`` env variable if you want to point
the alt-text pass at a different vision model.

Per-image results are cached in ``$XDG_CACHE_HOME/md2star/alt-text/`` keyed
by ``<image-md5>_<model>.txt`` so repeated runs over the same source tree
do not re-query Ollama.

Like the text lint, the transport is transparent: the ``md2star[ai]`` extra
routes through the official ``ollama`` client, and its absence falls back to
a hand-rolled :mod:`urllib.request` POST with no change in behaviour.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.request

from ..cache import cache_dir
from ..logging import get_logger
from . import _ollama_client
from .lint import (
    _default_lint_model,
    _ensure_model_pulled,
    _ping_ollama,
    is_ollama_installed,
)

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)

# Match ``![<empty>](src)`` outside of code blocks. The alt group is
# ``\s*`` so any combination of empty / whitespace alt qualifies; src is
# ``[^)]+`` to stop at the closing paren. A trailing ``{…}`` attribute
# block is *allowed* (this pass may run after ``fix_image_widths``).
_EMPTY_ALT_RE = re.compile(r"!\[(\s*)\]\(([^)]+)\)")

# Schemes we cannot read off disk to feed a vision model.
_URL_PREFIXES = ("http://", "https://", "//", "data:", "file://")

_ALT_PROMPT = (
    "Describe this image as concise alt-text for a screen reader. "
    "Follow W3C alt-text guidance: under ~125 characters, no \"image of\" "
    "or \"picture of\" prefix, describe the meaning and key information "
    "the image conveys (not its visual style). Reply with the alt-text "
    "only — no quotes, no markdown, no explanation."
)


def _default_alt_text_model() -> str:
    """Return the configured vision model tag.

    Honours ``MD2STAR_ALT_TEXT_MODEL`` first; otherwise falls back to the
    text lint's default (``gemma4:e2b-mlx`` on macOS, ``gemma4:e2b``
    elsewhere). Gemma 4 e2b is multimodal, so reusing the lint model
    means a single ``ollama pull`` covers both passes — no extra
    multi-gigabyte download just to draft alt-text.
    """
    override = os.environ.get("MD2STAR_ALT_TEXT_MODEL")
    if override:
        return override
    return _default_lint_model()


DEFAULT_ALT_TEXT_MODEL = _default_alt_text_model()


def _hash_file(path: str) -> str | None:
    """Return the first 16 hex of the file's MD5, or ``None`` on read error."""
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:16]
    except OSError:
        return None


def _generate_alt(image_path: str, model: str, timeout: float = 60.0) -> str | None:
    """Ask Ollama's vision model to describe *image_path* with *model*.

    Returns the trimmed response on success, ``None`` on any failure — the
    caller treats ``None`` as "leave the markdown unchanged". With the
    ``md2star[ai]`` extra the request goes through the official client;
    without it we base64-post to ``/api/generate`` ourselves. Both paths
    share the quote/whitespace cleanup below.
    """
    if _ollama_client.OLLAMA is not None:
        # ``[ai]`` extra installed → hand the image *path* to the client, which
        # owns the read + base64 encoding. Any failure returns None (skip).
        alt = _ollama_client.generate(
            model,
            _ALT_PROMPT,
            images=[image_path],
            options={"temperature": 0.2},
            timeout=timeout,
        )
    else:
        # Zero-dependency fallback: Ollama's vision API takes images as base64
        # in the JSON body, so read the bytes and encode. Unreadable file →
        # None ("leave markdown unchanged").
        try:
            with open(image_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode("ascii")
        except OSError:
            return None

        # stream=False so we get one complete JSON response; low temperature
        # keeps alt-text deterministic-ish and on-task rather than creative.
        payload = json.dumps({
            "model": model,
            "prompt": _ALT_PROMPT,
            "images": [img_b64],
            "stream": False,
            "options": {"temperature": 0.2},
        }).encode("utf-8")

        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "md2star/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        alt = data.get("response")

    # Shared cleanup across both transports. Strip any surrounding quotes the
    # model may have produced so the rendered alt reads as a label rather
    # than a sentence (matches the W3C-style examples we asked for).
    alt = (alt or "").strip().strip('"').strip("'").strip()
    return alt or None


def fill_empty_alt_text(
    content: str,
    base_dir: str = ".",
    model: str | None = None,
) -> str:
    """Replace ``![](src)`` empty-alt images with an LLM-generated description.

    Mirrors :func:`md2star.preprocessing.lint.lint_with_llm`'s safety net:
    if Ollama is missing, the daemon is unreachable, the vision model is
    not pulled (and cannot be pulled), or the request fails, the original
    content is returned unchanged. The pass is *never* load-bearing.
    """
    if model is None:
        model = _default_alt_text_model()

    # Three cheap pre-flight gates: no Ollama, no running daemon, or no model →
    # return the content untouched. This pass is never load-bearing.
    if not is_ollama_installed():
        return content
    if not _ping_ollama(2):
        # Don't spawn ``ollama serve`` from this pass — let the lint pass
        # own that side-effect. If the daemon isn't already up by now,
        # silently skip.
        return content
    if not _ensure_model_pulled(model):
        return content

    cache = cache_dir("alt-text")

    def _process(match: re.Match) -> str:
        """Draft (or reuse a cached) alt-text for one empty-alt image.

        Called once per :data:`_EMPTY_ALT_RE` match. Remote/data URIs,
        missing files, unreadable files, and empty generations all early-return
        the original ``![](src)`` so a single un-processable image never breaks
        the document. Successful descriptions are cached under the image's
        content hash so re-runs are free.

        Parameters
        ----------
        match : re.Match
            A match of :data:`_EMPTY_ALT_RE`; group 1 is the empty/whitespace
            alt, group 2 is the ``src``.

        Returns
        -------
        str
            The image with a generated alt inserted, or the original match
            unchanged when no description could be produced.
        """
        # Called once per empty-alt image. Any early return keeps the original
        # ``![](src)`` so a single un-processable image never breaks the doc.
        src = match.group(2)
        # Remote/data URIs can't be read off disk to feed the vision model.
        if src.startswith(_URL_PREFIXES):
            return match.group(0)
        # Relative srcs resolve against the document's dir (see base_dir).
        path = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if not os.path.exists(path):
            return match.group(0)

        img_hash = _hash_file(path)
        if img_hash is None:
            return match.group(0)
        # Cache key = image content hash + model, so re-runs are free and a
        # model swap re-generates. Sanitise ':' / '/' for a safe filename.
        safe_model = model.replace(":", "_").replace("/", "_")
        cache_file = cache / f"{img_hash}_{safe_model}.txt"

        # Reuse a cached description when present; otherwise call the model and
        # persist the result. An empty generation → keep the original markdown.
        if cache_file.exists():
            alt = cache_file.read_text(encoding="utf-8").strip()
        else:
            alt = _generate_alt(path, model)
            if not alt:
                return match.group(0)
            try:
                cache_file.write_text(alt, encoding="utf-8")
            except OSError as e:
                # A failed cache write is non-fatal: we still return the alt
                # text, we just don't persist it for next time.
                logger.warning(
                    f"md2star warning: could not cache alt-text for {path}: {e}"
                )

        # Escape any closing-bracket the model produced — would break the
        # Markdown image syntax otherwise.
        alt_clean = alt.replace("]", "\\]")
        return f"![{alt_clean}]({src})"

    # Walk line by line tracking fenced code blocks so we never rewrite an
    # ``![]()`` that's really a code sample. Only prose lines get _process.
    out_lines: list[str] = []
    in_code = False
    for line in content.split("\n"):
        # A ``` fence toggles code mode; the fence line itself is passed through.
        if line.lstrip().startswith("```"):
            in_code = not in_code
            out_lines.append(line)
            continue
        if in_code:
            out_lines.append(line)
            continue
        out_lines.append(_EMPTY_ALT_RE.sub(_process, line))
    return "\n".join(out_lines)
