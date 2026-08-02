"""AI diagram layer for the Markdown *twin*: classify, then reconstruct.

The deterministic twin core (:mod:`md2star.reverse`) scrapes every raster a
document carries and, by default, re-embeds each one verbatim as a PNG. This
module is the opt-in layer that makes the twin *editable*: it looks at each
scraped raster with a local vision model and decides what it really is —

* a **photo** (a screenshot, a portrait, a product shot): keep the PNG as-is;
* a **diagram** expressible as a graph (a flowchart, a sequence/box-and-arrow
  schematic): re-author it as **Mermaid** so it lives in the twin as *code*,
  round-trips through md2star's forward path, and diffs cleanly in git.

Reconstruction is verified, not trusted. Each Mermaid candidate is put through a
**target-matching Ralph Eyeball Loop** — render the candidate with the same
vendored ``mmdc`` the forward path uses, show *both* the candidate render and
the original scraped image to the vision model, ask what differs, and feed the
discrepancies back to the text model to revise the source. The loop repeats
until the model reports a match or the iteration budget is spent. On anything
short of a confident match the twin keeps the scraped PNG as a caption fallback,
so a poor reconstruction never loses the ground truth.

Everything here is **best-effort and never load-bearing**: if the ``[ai]``
stack, the Ollama daemon, the vision model, or ``mmdc`` is absent, every image
degrades to the plain scraped PNG — exactly what the deterministic core would
have produced. Models are chosen by the suite picker
(:mod:`best_engine_ai_helper`); nothing is hard-coded.

The public entry point is :func:`make_diagram_handler`, which returns an
:data:`md2star.reverse.ImageHandler` ready to hand to
:func:`md2star.reverse.to_markdown_twin`. All model/render calls are threaded
through injectable seams (*vlm* / *render*) so the loop is unit-testable offline
with fakes, no live daemon required.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import base64
import json
import re
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .logging import get_logger
from .preprocessing import _ollama_client
from .reverse import ImageHandler, TwinImage

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)

# A vision/text transport: given a prompt and zero or more image paths, return
# the model's text or ``None`` on any failure. The real implementation talks to
# Ollama; tests inject a fake so the loop runs without a daemon.
VlmFn = Callable[[str, list[str]], "str | None"]

# A candidate renderer: given a diagram kind ("mermaid") and its source, produce
# a PNG path or ``None`` if it could not be rendered. Defaults to the vendored
# ``mmdc`` path; injectable for tests.
RenderFn = Callable[[str, str], "str | None"]

# Reconstruction is currently offered for graph-expressible diagrams only, which
# ``mmdc`` renders and the eyeball loop can verify. Freeform figures (a plotted
# curve, a hand-drawn schematic) stay as scraped PNGs — SVG re-authoring is a
# planned follow-up that needs its own rasteriser for the loop.
RECONSTRUCTABLE_KINDS: frozenset[str] = frozenset({"mermaid"})


@dataclass
class _Verdict:
    """One eyeball-loop comparison result: does the candidate match the target?"""

    matches: bool
    discrepancies: str  # free-text notes the text model uses to revise the source


def _default_vlm(model: str) -> VlmFn:
    """Build the real Ollama-backed transport for *model*.

    Mirrors :func:`md2star.preprocessing.alt_text._generate_alt`: route through
    the official client when the ``[ai]`` extra is installed, else fall back to a
    zero-dependency base64 POST to ``/api/generate``. Returns ``None`` on any
    failure so the loop degrades to "keep the PNG".
    """

    def _call(prompt: str, image_paths: list[str]) -> str | None:
        # Preferred path: the typed client owns reading + base64-encoding images.
        if _ollama_client.OLLAMA is not None:
            return _ollama_client.generate(
                model,
                prompt,
                images=image_paths or None,
                options={"temperature": 0.0},
                timeout=90.0,
            )

        # Zero-dependency fallback: encode each image ourselves and post JSON.
        images_b64: list[str] = []
        for path in image_paths:
            try:
                with open(path, "rb") as handle:
                    images_b64.append(base64.b64encode(handle.read()).decode("ascii"))
            except OSError:
                return None  # an unreadable image means we cannot judge — skip

        payload = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "images": images_b64 or None,
                "stream": False,
                "options": {"temperature": 0.0},
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "md2star/1.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        text = (data.get("response") or "").strip()
        return text or None

    return _call


def _default_render() -> RenderFn:
    """Build the real candidate renderer, reusing the vendored ``mmdc`` path."""

    def _render(kind: str, source: str) -> str | None:
        if kind != "mermaid":
            return None  # only Mermaid is renderable in v1 (see RECONSTRUCTABLE_KINDS)
        # Reuse the exact renderer the forward path uses, so a candidate that
        # renders here will render identically when the twin is re-converted.
        from .preprocessing.mermaid import render_mermaid_local

        try:
            return render_mermaid_local(source, out_dir=".")
        except (RuntimeError, OSError) as exc:
            # mmdc/Node missing or a broken candidate — the loop treats a None
            # render as "cannot verify" and stops, keeping the best draft so far.
            logger.debug("candidate mermaid render failed: %s", exc)
            return None

    return _render


# ── prompts ────────────────────────────────────────────────────────────────
# Kept together and terse; each asks the model for a single machine-parseable
# token or a fenced block so parsing stays robust across model idiosyncrasies.

_CLASSIFY_PROMPT = (
    "You are triaging an image extracted from a document.\n"
    "Answer with EXACTLY ONE word:\n"
    "  DIAGRAM  — if it is a flowchart, block/box-and-arrow schematic, graph, "
    "sequence, state, class or entity diagram (something expressible as nodes "
    "and edges).\n"
    "  PHOTO    — anything else: a photograph, screenshot, logo, chart/plot, "
    "or freeform figure.\n"
    "Reply with only DIAGRAM or PHOTO."
)

_DRAFT_PROMPT = (
    "This image is a node-and-edge diagram. Reproduce it as a Mermaid diagram.\n"
    "Rules:\n"
    "- Output ONLY a single ```mermaid fenced code block, nothing else.\n"
    "- Choose the right diagram type (flowchart, sequenceDiagram, etc.).\n"
    "- Preserve every node label and every edge/arrow direction you can read.\n"
)

_COMPARE_PROMPT = (
    "The FIRST image is a target diagram. The SECOND image is a candidate "
    "reproduction.\n"
    "Do they convey the same nodes, labels and connections?\n"
    "Respond as JSON on one line: "
    '{"matches": true|false, "discrepancies": "<short list of what the '
    'candidate gets wrong or is missing, or empty if it matches>"}.'
)

_REVISE_PROMPT = (
    "Here is a Mermaid diagram that should reproduce a target, and a list of its "
    "discrepancies against that target. Fix the Mermaid source to resolve them.\n"
    "Output ONLY a single ```mermaid fenced code block.\n\n"
    "Current Mermaid:\n```mermaid\n{source}\n```\n\nDiscrepancies:\n{discrepancies}\n"
)

# Pull the body out of a ```mermaid ...``` block (the model is asked to emit
# exactly one); tolerant of a missing language tag and trailing whitespace.
_MERMAID_BLOCK_RE = re.compile(r"```(?:mermaid)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_mermaid(text: str | None) -> str | None:
    """Return the Mermaid source from a model reply, or ``None`` if absent."""
    if not text:
        return None
    match = _MERMAID_BLOCK_RE.search(text)
    body = (match.group(1) if match else text).strip()
    # A bare reply with no fence but a plausible header is still usable.
    return body or None


def _parse_verdict(text: str | None) -> _Verdict:
    """Parse the compare step's JSON reply into a :class:`_Verdict`.

    Defensive: models wrap JSON in prose or fences. We find the first ``{...}``
    span and parse it; anything unparseable is treated as "no match" so the loop
    keeps iterating rather than declaring a false success.
    """
    if not text:
        return _Verdict(matches=False, discrepancies="no response")
    span = re.search(r"\{.*\}", text, re.DOTALL)
    if span:
        try:
            obj = json.loads(span.group(0))
            return _Verdict(
                matches=bool(obj.get("matches")),
                discrepancies=str(obj.get("discrepancies") or "").strip(),
            )
        except (json.JSONDecodeError, TypeError):
            pass
    # Fallback heuristic: a plain "yes"/"match" with no JSON still counts.
    lowered = text.lower()
    matched = "true" in lowered or "matches" in lowered and "not" not in lowered
    return _Verdict(matches=matched, discrepancies="" if matched else text.strip())


def reconstruct_mermaid(
    target_png: str,
    *,
    vlm: VlmFn,
    render: RenderFn,
    max_iterations: int = 3,
) -> str | None:
    """Re-author *target_png* as Mermaid via the target-matching eyeball loop.

    Parameters
    ----------
    target_png : str
        Path to the scraped diagram image to reproduce.
    vlm : VlmFn
        Vision/text transport (draft, compare, revise all go through it).
    render : RenderFn
        Candidate renderer; ``("mermaid", source) -> png_path`` or ``None``.
    max_iterations : int, default 3
        Upper bound on render→compare→revise cycles.

    Returns
    -------
    str or None
        The best Mermaid source found (matched, or the closest draft when the
        budget runs out), or ``None`` if no usable draft could be produced.
    """
    # Step 0 — first draft: describe the diagram straight to Mermaid.
    source = _extract_mermaid(vlm(_DRAFT_PROMPT, [target_png]))
    if not source:
        return None  # the model could not even draft it — caller keeps the PNG

    for iteration in range(1, max_iterations + 1):
        candidate_png = render("mermaid", source)
        if candidate_png is None:
            # Cannot render (no mmdc, or broken source) → cannot verify. Return
            # the current draft best-effort; the caller pairs it with the PNG.
            logger.debug("eyeball loop: candidate unrenderable at iter %d", iteration)
            return source

        verdict = _parse_verdict(
            # Order matters: target first, candidate second (see _COMPARE_PROMPT).
            vlm(_COMPARE_PROMPT, [target_png, candidate_png])
        )
        if verdict.matches:
            logger.info("eyeball loop: matched target after %d iteration(s)", iteration)
            return source
        if iteration == max_iterations:
            break  # budget spent — keep the last (closest) source

        revised = _extract_mermaid(
            vlm(_REVISE_PROMPT.format(source=source, discrepancies=verdict.discrepancies), [])
        )
        if not revised or revised == source:
            break  # the model stopped improving — stop looping
        source = revised

    return source


@dataclass
class DiagramHandler:
    """Stateful :data:`ImageHandler` that classifies and reconstructs rasters.

    Instances are callables compatible with
    :func:`md2star.reverse.to_markdown_twin`'s ``image_handler`` seam. The scraped
    PNG is *always* written (it is the fallback and the ground truth); the
    Markdown returned is a Mermaid block (plus a commented PNG fallback) for a
    reconstructed diagram, or a plain image link otherwise.
    """

    vlm: VlmFn
    render: RenderFn
    max_iterations: int = 3

    def __call__(self, img: TwinImage, assets_dir: Path) -> str:
        # Always persist the raster first: even a perfect reconstruction keeps
        # the original as a caption fallback, and a failed one falls back to it.
        assets_dir.mkdir(parents=True, exist_ok=True)
        dest = assets_dir / img.suggested_name
        dest.write_bytes(img.data)
        rel = f"{assets_dir.name}/{dest.name}"

        kind = self._classify(str(dest))
        if kind != "diagram":
            # Photo / chart / freeform → keep the PNG (empty alt invites the
            # forward --lint alt-text pass to fill it later).
            return f"![]({rel})"

        source = reconstruct_mermaid(
            str(dest), vlm=self.vlm, render=self.render, max_iterations=self.max_iterations
        )
        if not source:
            return f"![]({rel})"  # could not reconstruct — the PNG stands alone

        # Mermaid becomes the primary, editable representation; the scraped PNG
        # rides along as an HTML comment so the ground truth is never lost and
        # the body stays clean when rendered.
        return f"```mermaid\n{source}\n```\n\n<!-- source figure: ![]({rel}) -->"

    def _classify(self, png_path: str) -> str:
        """Return ``"diagram"`` or ``"photo"`` for *png_path* (photo on doubt)."""
        reply = (self.vlm(_CLASSIFY_PROMPT, [png_path]) or "").strip().lower()
        # Default to "photo" on an empty/ambiguous reply: keeping a PNG is always
        # safe, whereas a wrong "diagram" wastes a full eyeball loop.
        return "diagram" if reply.startswith("diagram") else "photo"


def diagrams_available(model: str | None = None) -> bool:
    """Return ``True`` when diagram reconstruction can actually run.

    Checks the same pre-flight gates the alt-text pass uses (Ollama installed,
    daemon reachable, model pulled). Cheap enough to call before offering the
    feature in a UI or CLI ``--diagrams`` flag.
    """
    from .preprocessing.lint import _ensure_model_pulled, _ping_ollama, is_ollama_installed

    if not is_ollama_installed() or not _ping_ollama(2):
        return False
    return _ensure_model_pulled(model or _resolve_vision_model())


def _resolve_vision_model() -> str:
    """Resolve the vision model tag via the suite picker (or the alt-text override)."""
    # Reuse alt-text's resolution so ``MD2STAR_ALT_TEXT_MODEL`` and the
    # best-engine picker choice apply uniformly to every VLM pass in the tool.
    from .preprocessing.alt_text import _default_alt_text_model

    return _default_alt_text_model()


def make_diagram_handler(
    *,
    model: str | None = None,
    max_iterations: int = 3,
    vlm: VlmFn | None = None,
    render: RenderFn | None = None,
) -> ImageHandler:
    """Return an :data:`ImageHandler` that classifies and reconstructs diagrams.

    Parameters
    ----------
    model : str, optional
        Vision model tag. Defaults to the suite picker's choice.
    max_iterations : int, default 3
        Eyeball-loop budget per diagram.
    vlm, render : optional
        Injectable transport/renderer seams (defaults talk to Ollama + ``mmdc``).
        Supplying fakes makes the whole layer unit-testable offline.

    Returns
    -------
    ImageHandler
        A callable ready for :func:`md2star.reverse.to_markdown_twin`.
    """
    resolved_model = model or _resolve_vision_model()
    handler = DiagramHandler(
        vlm=vlm or _default_vlm(resolved_model),
        render=render or _default_render(),
        max_iterations=max_iterations,
    )
    return handler
