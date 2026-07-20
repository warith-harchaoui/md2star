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

Language + context (aligned with the suite's ``front-vision`` skill):

* The alt text is written in the **document's own language**, auto-detected from
  the surrounding prose (any language, not a hardcoded EN/FR toggle) — a French
  document gets French alt text. English is the fallback when detection fails.
* Each image's **surrounding text** (nearest heading + nearby prose) is passed
  to the model so it describes what the image *means* in place, not just its
  pixels.

The vision model defaults to ``gemma3:4b`` — the suite's authorized, reliably
multimodal model (the same tag ``front-vision`` uses). We deliberately do NOT
share the text-lint model: the macOS lint default ``gemma4:e2b-mlx`` is a
text-only MLX build that cannot see images. Override with
``MD2STAR_ALT_TEXT_MODEL``.

Per-image results are cached in ``$XDG_CACHE_HOME/md2star/alt-text/`` keyed by
``<image-md5>_<model>_<lang+context-hash>.txt`` so a re-run in a different
language or surrounding context re-drafts rather than serving a stale caption.

Like the text lint, the transport is transparent: the ``md2star[ai]`` extra
routes through the official ``ollama`` client, and its absence falls back to
a hand-rolled :mod:`urllib.request` POST with no change in behaviour.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.request

import os_helper as osh

from ..cache import cache_dir
from ..logging import get_logger
from . import _ollama_client
from .language import get_language_metadata
from .lint import (
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

# 2-letter code → English language name. Used to tell the model which language
# to write the alt text in — ``"Write the alt text in French."`` — supporting ANY
# detected language (not a bilingual EN/FR lock). Codes we can't name fall back
# to English so a strange language never breaks the prompt.
_LANG_NAMES: dict[str, str] = {
    "en": "English", "fr": "French", "es": "Spanish", "de": "German",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "ru": "Russian",
    "zh": "Chinese", "ja": "Japanese", "ko": "Korean", "ar": "Arabic",
    "hi": "Hindi", "tr": "Turkish", "pl": "Polish", "sv": "Swedish",
    "no": "Norwegian", "da": "Danish", "fi": "Finnish", "cs": "Czech",
    "el": "Greek", "he": "Hebrew", "id": "Indonesian", "uk": "Ukrainian",
    "ro": "Romanian", "hu": "Hungarian", "vi": "Vietnamese", "th": "Thai",
}


def _build_alt_prompt(lang_name: str, context: str) -> str:
    """Assemble the per-image W3C alt-text prompt in *lang_name*, biased by *context*.

    Mirrors the front-vision skill's approach — write in the document's language,
    lean on the surrounding text for meaning — kept as one lean self-contained
    prompt rather than that skill's full per-purpose decision tree.

    Parameters
    ----------
    lang_name : str
        English name of the target output language (e.g. ``"French"``).
    context : str
        Surrounding document text (heading + nearby prose), or ``""``.

    Returns
    -------
    str
        The complete instruction sent to the vision model.
    """
    # Only add the context clause when we actually found surrounding text, and
    # tell the model to use it for *meaning* — not to quote it back.
    ctx_line = (
        f" Surrounding document text (use it to judge what the image means "
        f"in context — do not quote it): {context}"
        if context else ""
    )
    return (
        f"Write concise alt text for this image in {lang_name}, for a screen "
        f"reader.{ctx_line} Follow W3C guidance: under ~125 characters; describe "
        f"the meaning and key information the image conveys (not its visual "
        f"style); do not start with \"image of\" / \"picture of\" or the "
        f"equivalent in {lang_name}. Reply with the alt text only — no quotes, "
        f"no markdown, no explanation."
    )


def _detect_alt_language(content: str) -> str:
    """Return the English name of *content*'s language (auto-detected, ``English`` fallback).

    Language is detected from the document body itself (no configured default),
    so alt text comes out in the same language the surrounding prose is written
    in. Degrades to English when ``langdetect`` is absent or the text is too
    short to classify.
    """
    meta = get_language_metadata(content)
    # get_language_metadata returns e.g. {"lang": "en-US"} / {"lang": "fr"} or
    # None; take the 2-letter base and map it to a display name.
    code = (meta or {}).get("lang", "en").split("-")[0].lower()[:2]
    return _LANG_NAMES.get(code, "English")


# Match a Markdown ATX heading line, used to prepend the nearest section title
# to an image's surrounding-text context.
_HEADING_RE = re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE)


def _surrounding_context(content: str, src: str, window: int = 280) -> str:
    """Return the document text around the image *src*, capped and heading-prefixed.

    Finds where *src* is referenced in *content*, keeps ``window`` characters on
    each side, strips Markdown image/link syntax to leave prose, and prepends the
    nearest preceding heading so the model knows the section the image sits in.
    Returns ``""`` when the reference cannot be located.
    """
    pos = content.find(src)
    if pos == -1:
        return ""
    # Grab a window either side of the reference and drop the image/link syntax
    # so the model sees prose, not URLs.
    chunk = content[max(0, pos - window): pos + len(src) + window]
    chunk = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", chunk)      # images → drop
    chunk = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", chunk)    # links → label
    chunk = re.sub(r"[#>*_`~]+", " ", chunk)                  # md punctuation
    chunk = " ".join(chunk.split())

    # Prepend the nearest heading before the image for section context.
    heading = ""
    for m in _HEADING_RE.finditer(content, 0, pos):
        heading = m.group(1).strip("# ").strip()
    prefix = f"{heading}. " if heading else ""
    return (prefix + chunk).strip()[: 2 * window]


# Default vision model for alt-text. ``gemma3:4b`` is the suite's authorized
# vision model (the front-vision skill uses the same tag): a compact, reliably
# multimodal build. We deliberately do NOT reuse the text-lint default here —
# the macOS lint model ``gemma4:e2b-mlx`` is an MLX text build that does not
# process images, so sharing it produced empty/garbage alt text. A separate
# ``ollama pull`` for a model that can actually see is the right trade.
_DEFAULT_ALT_MODEL = "gemma3:4b"


def _default_alt_text_model() -> str:
    """Return the configured vision model tag.

    Honours ``MD2STAR_ALT_TEXT_MODEL`` first; otherwise uses the suite's
    authorized vision model :data:`_DEFAULT_ALT_MODEL` (``gemma3:4b``), which —
    unlike the text-lint default — actually processes images on every platform.
    """
    override = os.environ.get("MD2STAR_ALT_TEXT_MODEL")
    if override:
        return override
    return _DEFAULT_ALT_MODEL


DEFAULT_ALT_TEXT_MODEL = _default_alt_text_model()


def _hash_file(path: str) -> str | None:
    """Return the first 16 hex of the file's content hash, or ``None`` on error.

    ``None`` signals "unreadable — skip caching for this image". We guard with
    ``osh.file_exists`` first because ``osh.hashfile`` falls back to hashing the
    *path* for a missing file (a valid-looking but wrong key); the ``OSError``
    guard then covers an existing-but-unreadable file.
    """
    if not osh.file_exists(path):
        return None
    try:
        return osh.hashfile(path)[:16]
    except OSError:
        return None


def _generate_alt(
    image_path: str, model: str, prompt: str, timeout: float = 60.0
) -> str | None:
    """Ask Ollama's vision model to describe *image_path* using *prompt*.

    *prompt* is the per-image instruction built by :func:`_build_alt_prompt`
    (target language + surrounding-text context). Returns the trimmed response
    on success, ``None`` on any failure — the caller treats ``None`` as "leave
    the markdown unchanged". With the ``md2star[ai]`` extra the request goes
    through the official client; without it we base64-post to ``/api/generate``
    ourselves. Both paths share the quote/whitespace cleanup below.
    """
    if _ollama_client.OLLAMA is not None:
        # ``[ai]`` extra installed → hand the image *path* to the client, which
        # owns the read + base64 encoding. Any failure returns None (skip).
        alt = _ollama_client.generate(
            model,
            prompt,
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
            "prompt": prompt,
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

    # Detect the document's language ONCE (not per image): alt text is written
    # in the same language as the surrounding prose. Auto-detected from the body,
    # no configured default (English fallback when undetectable).
    lang_name = _detect_alt_language(content)

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

        # Surrounding-document context (nearest heading + nearby prose) so the
        # model describes what the image *means* in place, not just its pixels.
        context = _surrounding_context(content, src)
        prompt = _build_alt_prompt(lang_name, context)

        # Cache key folds the image content, model, language, and a short hash of
        # the context+language so a re-run in a different language or context
        # re-drafts rather than serving a stale caption. Sanitise ':' / '/'.
        safe_model = model.replace(":", "_").replace("/", "_")
        ctx_key = osh.hash_string(f"{lang_name}\x00{context}", 10)
        cache_file = cache / f"{img_hash}_{safe_model}_{ctx_key}.txt"

        # Reuse a cached description when present; otherwise call the model and
        # persist the result. An empty generation → keep the original markdown.
        if cache_file.exists():
            alt = cache_file.read_text(encoding="utf-8").strip()
        else:
            alt = _generate_alt(path, model, prompt)
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
