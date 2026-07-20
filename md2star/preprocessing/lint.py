"""Opt-in LLM-powered Markdown syntax linter (via Ollama).

Resolution policy (off by default):

* No flag, or ``--no-lint``     → skip the lint entirely.
* ``--lint`` + Ollama installed → run the lint, spawning ``ollama serve``
                                  and ``ollama pull``-ing the default model
                                  on demand if either is missing.
* ``--lint`` + Ollama missing   → print a one-line warning on stderr and
                                  fall back to the original Markdown so
                                  the overall conversion still succeeds.

The opt-in default keeps conversions deterministic and side-effect-free.
Pass ``--lint`` explicitly when you want the LLM to fix obvious syntax
issues (broken image links, unclosed code fences, malformed table pipes)
before Pandoc parses the file.

When enabled, :func:`lint_with_llm` sends the document to Ollama and keeps
the response only if it passes a coarse length-sanity check (0.5×–2× of
the original). Any failure (network error, suspicious output, pull failure)
falls back to the original content unchanged — the lint is never
load-bearing for a successful conversion.

The default model is a small text-only Gemma 4 variant — ``gemma4:e2b-mlx``
on macOS (Apple-Silicon-optimized MLX build) and ``gemma4:e2b`` everywhere
else. Both are tiny enough to fit on most laptops without breaking a sweat.
Set the ``MD2STAR_LINT_MODEL`` env variable to override the default tag
without editing code (useful on private registries or for trying a larger
model).

Transport is transparent: with the optional ``md2star[ai]`` extra installed
the request goes through the official ``ollama`` Python client (via
:mod:`md2star.preprocessing._ollama_client`); without it the same request is
sent with a hand-rolled :mod:`urllib.request` POST. Behaviour is identical
either way — the extra only buys the ergonomic typed client, never a
different result.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request

import os_helper as osh

from ..logging import get_logger
from . import _ollama_client

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)


def _default_lint_model() -> str:
    """Return the default Ollama tag, honoring ``MD2STAR_LINT_MODEL`` if set."""
    # Explicit override wins (lets users pin a bigger/smaller model). Otherwise
    # pick the MLX build on macOS — it's the Apple-Silicon-optimised variant —
    # and the plain build everywhere else.
    override = os.environ.get("MD2STAR_LINT_MODEL")
    if override:
        return override
    return "gemma4:e2b-mlx" if osh.macos() else "gemma4:e2b"


DEFAULT_LINT_MODEL = _default_lint_model()


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


def _fetch_ollama_models(timeout: float = 2.0) -> list[str] | None:
    """Return installed model names from ``/api/tags``, or None if unreachable."""
    # Fast path: with the ``md2star[ai]`` extra the official client answers the
    # same query with a typed response. It returns None when the extra is
    # absent, in which case we fall through to the zero-dependency urllib probe.
    if _ollama_client.OLLAMA is not None:
        return _ollama_client.list_model_names(timeout)
    # /api/tags lists locally-pulled models. A broad except → None means
    # "daemon unreachable"; callers treat that as "no models" and degrade
    # gracefully rather than surfacing a connection error to the user.
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/tags",
            headers={"User-Agent": "md2star/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    # Keep only non-empty model names from the response.
    return [m.get("name", "") for m in data.get("models", []) if m.get("name")]


def _ping_ollama(timeout: float = 2.0) -> bool:
    """Cheap reachability probe for the local Ollama HTTP API."""
    return _fetch_ollama_models(timeout) is not None


def is_ollama_installed() -> bool:
    """True iff the ``ollama`` binary is reachable on ``PATH``.

    Used as the auto-enable gate for lint: if the user does not have Ollama
    installed at all, we stay completely silent. If they do, we take care
    of starting the daemon and pulling the model on demand — the rationale
    being "the tool is here, so use it without asking".
    """
    return shutil.which("ollama") is not None


def _model_present(model: str, timeout: float = 2.0) -> bool:
    """Return True if *model* is already pulled and the daemon can see it."""
    names = _fetch_ollama_models(timeout)
    # Daemon unreachable → treat the model as absent (caller will try a pull).
    if names is None:
        return False
    # Exact tag match is the common case.
    if model in names:
        return True
    # Ollama stores untagged pulls as ``name:latest``; tolerate that form so a
    # user who ran ``ollama pull gemma4:e2b`` isn't told it's missing.
    if ":" not in model and f"{model}:latest" in names:
        return True
    return False


def _ensure_model_pulled(model: str) -> bool:
    """Make sure *model* is locally available; ``ollama pull`` it if not.

    Returns True on success, False if the pull failed (network down,
    bad model name, …) — the caller falls back to the original content
    rather than letting the conversion error out.
    """
    if _model_present(model):
        return True

    # Progress narration (INFO): a first-run model pull can take minutes, so
    # tell the user why the command appears to hang.
    logger.info(
        f"md2star: lint model {model!r} missing; running `ollama pull "
        f"{model}` (one-time download)…"
    )
    # 15-minute cap covers a multi-GB first pull on a slow link; we discard
    # the progress bar (DEVNULL) but keep stderr to surface a real error.
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=900,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        # Binary vanished or the pull ran too long → give up on lint, not crash.
        logger.warning(f"md2star warning: model pull failed: {e}")
        return False

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        logger.warning(
            f"md2star warning: `ollama pull {model}` exited "
            f"{result.returncode}: {stderr}"
        )
        return False
    return True


def _ensure_ollama_running() -> bool:
    """Return True if Ollama is responding; try to spawn it once if not.

    Only invoked when the user passed ``--lint`` *explicitly* (auto-enabled
    lint never reaches this path — it gives up immediately if the daemon is
    not already running). The spawn is narrated on stderr so the user knows
    a long-lived process was started on their behalf.
    """
    if _ping_ollama(2):
        return True

    # Narrate the background spawn (INFO): we start a long-lived `ollama serve`
    # on the user's behalf, so it should not be silent.
    logger.info(
        "md2star: --lint requested but no Ollama instance answered on "
        "localhost:11434; starting `ollama serve` in the background."
    )

    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        logger.warning(
            "md2star: `ollama` executable not found; skipping lint. "
            "Install Ollama from https://ollama.com to enable --lint."
        )
        return False

    # Poll for up to ~5s (10 × 0.5s) while the freshly-spawned daemon boots.
    # If it never answers, give up so lint stays strictly best-effort.
    for _ in range(10):
        time.sleep(0.5)
        if _ping_ollama(1):
            return True
    return False


def lint_with_llm(content: str, model: str | None = None) -> str:
    """Send *content* to Ollama for syntax-only fixes; return original on any failure.

    The 0.5×–2× length guard is a coarse hallucination/truncation check; if
    the response strays outside that band, the original is kept. The full
    resolution path is: Ollama missing → warn + fall back to original;
    daemon down → spawn it; model missing → ``ollama pull`` it; then run
    the request. *model* defaults to :data:`DEFAULT_LINT_MODEL` (which
    honors the ``MD2STAR_LINT_MODEL`` env override).
    """
    # Resolve the model once (env override or per-OS default) up front.
    if model is None:
        model = _default_lint_model()

    if not is_ollama_installed():
        # --lint is opt-in; if the dependency is missing we degrade to a no-op
        # rather than failing the whole conversion.
        logger.warning(
            "md2star: --lint requested but `ollama` is not installed; "
            "skipping the lint pass. Install Ollama from "
            "https://ollama.com to enable it."
        )
        return content
    # Remaining gates spawn the daemon / pull the model as needed; any failure
    # short-circuits to the untouched content.
    if not _ensure_ollama_running():
        return content
    if not _ensure_model_pulled(model):
        return content

    try:
        # temperature=0.0 for a deterministic, minimal syntax fix — we want a
        # corrector, not a creative rewriter. The prompt precedes the document.
        prompt = _LINT_PROMPT + "\n\n" + content
        if _ollama_client.OLLAMA is not None:
            # ``[ai]`` extra installed → route through the official client; it
            # returns the trimmed response or None (which we map to the empty
            # string so the shared "keep original" guards below apply).
            fixed = _ollama_client.generate(
                model, prompt, options={"temperature": 0.0}, timeout=30
            ) or ""
        else:
            # Zero-dependency fallback: POST to /api/generate ourselves.
            payload = json.dumps({
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0},
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
            # 30s cap on the whole request; the response holds the fixed markdown.
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                fixed = result.get("response", "").strip()

        # Empty response → nothing to apply, keep the original.
        if not fixed:
            return content
        # Compare lengths as a cheap sanity check (see the guard just below).
        original_len = len(content.strip())
        fixed_len = len(fixed)
        if fixed_len < original_len * 0.5 or fixed_len > original_len * 2.0:
            # Coarse hallucination/truncation guard: a wildly different length
            # means we distrust the model and keep the original untouched.
            logger.warning(
                "md2star warning: LLM lint output size too different, skipping"
            )
            return content

        # Passed the length sanity check → accept the model's corrected markdown.
        return fixed

    except Exception as e:
        # Any failure (network, JSON, decode) is non-fatal — keep the original.
        logger.warning(f"md2star warning: LLM lint failed: {e}")
        return content
