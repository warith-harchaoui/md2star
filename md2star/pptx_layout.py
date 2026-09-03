"""Template-intelligent PPTX layout catalog and per-slide AI selection.

Pandoc's PPTX writer only ever reaches the ~7 named layouts its bundled
``template.pptx`` ships (``Title Slide``, ``Section Header``, ``Title and
Content``, ...); it has no notion of a *designer* template's much richer
layout vocabulary (a real marketing deck template routinely ships 20-40 named
layouts: covers, section dividers, big-statement slides, photo heroes,
multi-column splits, ...). This module is the missing primitive: given any
designer PPTX template, it builds a **layout catalog** (every distinct named
layout, its placeholder geometry, and — when a vision model is available — a
short caption of what kind of slide it is), then **selects** the best-fitting
catalog layout for each slide of an authored Markdown deck.

Selection is two-staged, mirroring how a human designer would actually work:

1. **Text reasoning** (LLM): read each slide's Markdown content plus the
   catalog (names + captions) and choose the layout whose *role* best fits —
   a cover, a section divider, a photo hero, bulleted content, ... This stage
   alone is cheap and works from captions only, never looking at a candidate
   render.
2. **Visual confirmation** (VLM): the text stage never actually *looks* at
   the candidate layouts, so it can pick a layout whose caption sounds right
   but whose actual composition does not suit the slide (a "photo-hero"
   caption on a layout whose picture placeholder is tiny, say). This stage
   shows the vision model the slide's short-listed candidate thumbnails
   (the text pick plus a couple of archetype-diverse alternates) side by side
   and asks which one *actually* carries the content best, overriding the
   text pick on disagreement. This is the dimension a pure-LLM, caption-only
   selector cannot provide.

Both stages, and the template-page renderer they rely on, are threaded
through injectable seams (``chat`` / ``render``) so the whole pipeline is
unit-testable offline with fakes, exactly like :mod:`md2star.reverse_diagrams`.
Every call degrades gracefully: with no reachable engine the catalog still
builds (deterministic layout/placeholder extraction never needs AI) and
selection falls back to a safe, rule-based default layout per slide.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

import os_helper as osh
from best_engine_ai_helper import llm

from ._engine import engine
from .cache import cache_dir
from .logging import get_logger

logger = get_logger(__name__)

# ── transport seams ──────────────────────────────────────────────────────────
# A model call: prompt text, optional raw image bytes, optional JSON schema for
# structured output -> the parsed dict (when a schema is given), a plain str,
# or None on any failure. The real implementation routes through md2star's
# resolved engine; tests inject a fake so nothing here needs a live daemon.
ChatFn = Callable[[str, "list[bytes] | None", "dict | None"], "dict | str | None"]

# A template-page renderer: template path, 1-based page number -> PNG bytes, or
# None if the page could not be rendered (no LibreOffice/poppler, bad page).
RenderFn = Callable[[Path, int], "bytes | None"]

_NS = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

# Small, role-oriented vocabulary both the captioner and the selector target.
# Kept short on purpose: a coarse, reliable archetype beats a large taxonomy an
# 8-14B local model cannot use reliably.
ARCHETYPES: tuple[str, ...] = (
    "cover",
    "section-divider",
    "big-statement",
    "big-number",
    "bulleted-content",
    "two-column-split",
    "photo-hero",
    "process-steps",
    "quote",
    "closing",
    "reference-non-content",
)

# Layout names whose role is obviously "designer reference material" (colour
# palettes, logo sheets, icon grids), never a home for authored content. Used
# only as the *fallback* heuristic when no vision model is available to judge
# ``is_content_layout`` properly.
_REFERENCE_NAME_HINTS = ("colour", "color", "palette", "logo", "icon", "brand guide")


# ── data model ────────────────────────────────────────────────────────────────
@dataclass
class Placeholder:
    """One placeholder shape on a layout: its role and its box in EMU."""

    idx: int
    kind: str  # pandoc/OOXML placeholder type: title, body, pic, ctrTitle, ...
    emu: tuple[int, int, int, int] | None = None  # left, top, width, height


@dataclass
class LayoutInfo:
    """One distinct named layout the designer template exposes."""

    name: str
    example_pages: list[int] = field(default_factory=list)
    placeholders: list[Placeholder] = field(default_factory=list)
    archetype: str = "bulleted-content"
    background: str = ""
    caption: str = ""
    is_content_layout: bool = True

    @property
    def rep_page(self) -> int | None:
        """The first example slide page this layout appears on, if any."""
        return self.example_pages[0] if self.example_pages else None

    def has_kind(self, kind: str) -> bool:
        return any(p.kind == kind for p in self.placeholders)


@dataclass
class Slide:
    """One Markdown slide plus the cheap structural cues a selector keys on."""

    index: int
    title: str
    body: str = ""
    features: list[str] = field(default_factory=list)
    chosen_layout: str | None = None
    chosen_confidence: float | None = None
    chosen_why: str = ""
    # Bounded per-slide adjustments the target-matching eyeball loop
    # (:mod:`md2star.pptx_assemble`) writes back after judging a render against
    # the chosen layout's thumbnail: font_delta (pt, title/body), bullets (max
    # bullet count), img_grow (fractional image box growth). Empty = no change.
    overrides: dict = field(default_factory=dict)


# ── deterministic catalog extraction (no AI, always available) ──────────────
def _layout_example_pages(template: Path) -> dict[str, list[int]]:
    """Map each designer layout name to the slide pages that use it.

    A layout is captioned from *several* of its own examples (not just the
    first) so the caption describes the reusable design, not one example
    slide's filler content.
    """
    pages: dict[str, list[int]] = {}
    with zipfile.ZipFile(template) as z:
        names = set(z.namelist())
        n_slides = sum(1 for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n))
        for n in range(1, n_slides + 1):
            rel = f"ppt/slides/_rels/slide{n}.xml.rels"
            if rel not in names:
                continue
            m = re.search(r"slideLayouts/(slideLayout\d+)\.xml", z.read(rel).decode("utf-8"))
            if not m:
                continue
            lay_xml = z.read(f"ppt/slideLayouts/{m.group(1)}.xml").decode("utf-8")
            nm = re.search(r'<p:cSld name="([^"]*)"', lay_xml)
            pages.setdefault(nm.group(1) if nm else m.group(1), []).append(n)
    return pages


def _all_layout_files(template: Path) -> list[str]:
    """Every ``slideLayoutN.xml`` part in *template*, regardless of usage."""
    with zipfile.ZipFile(template) as z:
        return sorted(
            n for n in z.namelist() if re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", n)
        )


def _layout_name(template: Path, layout_part: str) -> str:
    """The designer-authored ``<p:cSld name="...">`` for one layout part."""
    with zipfile.ZipFile(template) as z:
        xml = z.read(layout_part).decode("utf-8")
    m = re.search(r'<p:cSld name="([^"]*)"', xml)
    return m.group(1) if m else Path(layout_part).stem


def _placeholder_kind(sp: ET.Element) -> str | None:
    # <p:ph> with no ``type`` attribute is OOXML's own shorthand for "body"
    # (the spec's default), not "untyped" — so we resolve it here rather than
    # leaving callers to special-case an empty string.
    ph = sp.find("./p:nvSpPr/p:nvPr/p:ph", _NS)
    if ph is None:
        return None
    return ph.get("type") or "body"


def _placeholder_idx(sp: ET.Element) -> int:
    ph = sp.find("./p:nvSpPr/p:nvPr/p:ph", _NS)
    idx = ph.get("idx") if ph is not None else None
    try:
        return int(idx) if idx is not None else 0
    except ValueError:
        # A non-numeric idx would mean malformed XML from a third-party
        # export tool; degrade to placeholder 0 rather than raise, since a
        # slightly wrong idx only affects placement-matching, never crashes.
        return 0


def _placeholder_emu(sp: ET.Element) -> tuple[int, int, int, int] | None:
    xfrm = sp.find("./p:spPr/a:xfrm", _NS)
    if xfrm is None:
        # No explicit <a:xfrm> is normal, not an error: the shape then
        # inherits its box from the corresponding placeholder on the slide
        # master. We don't resolve that inheritance chain here — callers
        # (pptx_assemble) fall back to a fractional default box instead.
        return None
    off, ext = xfrm.find("a:off", _NS), xfrm.find("a:ext", _NS)
    if off is None or ext is None:
        return None
    try:
        return (int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy")))
    except (TypeError, ValueError):
        return None


def _layout_placeholders(template: Path, layout_file: str) -> list[Placeholder]:
    """Parse one ``slideLayoutN.xml``'s ``<p:sp>`` placeholders (type/idx/box)."""
    with zipfile.ZipFile(template) as z:
        xml = z.read(f"ppt/slideLayouts/{layout_file}")
    root = ET.fromstring(xml)  # noqa: S314 — trusted local template file, not untrusted input
    out: list[Placeholder] = []
    # Fully-qualified tag name: ElementTree's ``iter`` doesn't accept the
    # ``_NS`` prefix map used by ``find``/``findall``, so the namespace has to
    # be spelled out in Clark notation here.
    for sp in root.iter("{http://schemas.openxmlformats.org/presentationml/2006/main}sp"):
        kind = _placeholder_kind(sp)
        if kind is None:
            continue  # a decorative (non-placeholder) shape — not tracked
        out.append(Placeholder(idx=_placeholder_idx(sp), kind=kind, emu=_placeholder_emu(sp)))
    return out


def layout_pages(template: Path) -> dict[str, list[int]]:
    """Public wrapper over :func:`_layout_example_pages` (used by callers/tests)."""
    return _layout_example_pages(template)


def extract_layouts(template: Path) -> list[LayoutInfo]:
    """Deterministically extract every distinct layout name and its geometry.

    No AI, no rendering: pure ``zipfile`` + ``ElementTree`` over the template's
    OOXML parts. Always available, and the first stage of :func:`build_catalog`.

    Enumerates every ``ppt/slideLayouts/slideLayoutN.xml`` part directly (not
    only the layouts some slide happens to use) so a template distributed with
    no example slides at all — just its layouts, e.g. python-pptx's own bundled
    default template — still yields a full catalog; ``example_pages`` is simply
    empty for a layout no slide currently demonstrates (no thumbnail/caption
    for it, but its geometry is still extracted and it can still be selected).
    """
    pages = _layout_example_pages(template)
    infos: list[LayoutInfo] = []
    seen: set[str] = set()
    for layout_part in _all_layout_files(template):
        name = _layout_name(template, layout_part)
        if name in seen:
            continue  # two parts sharing a designer-authored name — keep the first
        seen.add(name)
        placeholders = _layout_placeholders(template, layout_part.rsplit("/", 1)[-1])
        # Cheap heuristic used only until (or unless) a VLM caption overrides
        # it in build_catalog(): a designer's own naming is usually a strong
        # enough signal to keep colour/logo/icon reference pages out of the
        # content-selection pool even with no vision model available.
        is_reference = any(hint in name.lower() for hint in _REFERENCE_NAME_HINTS)
        infos.append(
            LayoutInfo(
                name=name,
                example_pages=pages.get(name, []),
                placeholders=placeholders,
                is_content_layout=not is_reference,
            )
        )
    infos.sort(key=lambda i: -len(i.example_pages))
    return infos


# ── template page rendering (LibreOffice + poppler; optional) ───────────────
def _find_soffice() -> str | None:
    """Locate ``soffice``, reusing the CLI's resolver to avoid drift."""
    try:
        from .cli import _find_soffice as _cli_find_soffice  # noqa: PLC0415

        return _cli_find_soffice()
    except ImportError:
        path = shutil.which("soffice") or shutil.which("libreoffice")
        if path:
            return path
        mac_app = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        return mac_app if Path(mac_app).exists() else None


def _render_all_pages(template: Path, *, dpi: int = 110) -> dict[int, bytes]:
    """Render every page of *template* to PNG bytes, keyed by 1-based page.

    ``soffice --headless --convert-to pdf`` then ``pdftoppm -png``. Returns an
    empty dict (never raises) when LibreOffice or ``pdftoppm`` is absent, or the
    conversion otherwise fails — callers degrade to caption-less catalogs.
    """
    soffice = _find_soffice()
    pdftoppm = shutil.which("pdftoppm")
    if soffice is None or pdftoppm is None:
        logger.debug("template rendering unavailable (soffice=%s, pdftoppm=%s)", soffice, pdftoppm)
        return {}
    try:
        # A fresh temp dir per call: soffice writes its PDF next to nothing we
        # control (it derives the output name from the input stem), so an
        # isolated dir is the simplest way to avoid collisions across calls.
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", d, str(template)],
                check=True,
                capture_output=True,
                timeout=180,
            )
            pdf = Path(d) / (template.stem + ".pdf")
            if not pdf.exists():
                return {}
            # 110dpi is the PoC's own validated choice: enough detail for a
            # VLM caption/compare pass, small enough that a 20-40 layout
            # template renders and uploads quickly.
            subprocess.run(
                [pdftoppm, "-png", "-r", str(dpi), str(pdf), f"{d}/p"],
                check=True,
                capture_output=True,
                timeout=180,
            )
            out: dict[int, bytes] = {}
            for f in sorted(Path(d).glob("p-*.png")):
                out[int(f.stem.split("-")[-1])] = f.read_bytes()
            return out
    except (subprocess.SubprocessError, OSError) as exc:
        # A timed-out or crashed soffice/pdftoppm must not be fatal — the
        # caller's catalog build just proceeds without captions/thumbnails.
        logger.debug("template render failed: %s", exc)
        return {}


def render_deck_pages(path: Path, *, dpi: int = 110) -> dict[int, bytes]:
    """Render every page of a PPTX/PDF *path* to PNG bytes, keyed by 1-based page.

    Public wrapper over :func:`_render_all_pages`, used by
    :mod:`md2star.pptx_assemble`'s eyeball loop to render its own assembled
    output (as opposed to :func:`default_render`, which caches per *template*
    page and is meant for the catalog/tie-break stages).
    """
    return _render_all_pages(path, dpi=dpi)


def default_render() -> RenderFn:
    """Build the real page renderer, caching all pages per template (by hash)."""
    # Keyed by content hash (not path) so the same template opened from two
    # different paths still shares one render pass, and an edited-in-place
    # template correctly triggers a fresh one. One soffice invocation renders
    # every page of the template at once, so caching per-template rather than
    # per-page avoids re-running it for each of a catalog's 20-40 layouts.
    _cache: dict[str, dict[int, bytes]] = {}

    def _render(template: Path, page: int) -> bytes | None:
        key = osh.hashfile(str(template))
        if key not in _cache:
            _cache[key] = _render_all_pages(template)
        return _cache[key].get(page)

    return _render


def default_chat(*, kind: str, model: str | None = None) -> ChatFn:
    """Build the real engine-backed transport for *kind* (``"llm"`` or ``"vlm"``).

    Routes through ``best_engine_ai_helper.llm.chat`` using md2star's resolved
    brief -> engine descriptor, exactly like :mod:`md2star.reverse_diagrams`.
    Returns ``None`` on any failure so callers degrade gracefully.
    """

    def _call(
        prompt: str, images: list[bytes] | None, json_schema: dict | None
    ) -> dict | str | None:
        try:
            # temperature=0.0: every call here is a classification/selection
            # decision with a strict schema, not creative prose — determinism
            # matters more than variety, and it makes re-runs reproducible.
            return llm.chat(
                prompt,
                engine=engine(),
                kind=kind,
                images=images,
                json_schema=json_schema,
                temperature=0.0,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001 — any failure -> caller falls back
            logger.debug("%s transport failed: %s", kind, exc)
            return None

    return _call


def smart_layout_available() -> bool:
    """Return ``True`` when the full AI-assisted pipeline (LLM + VLM) can run.

    Mirrors :func:`md2star.reverse_diagrams.diagrams_available`: a light "does
    the engine resolve and expose both model kinds?" probe, cheap enough to
    call before offering ``--smart-layout`` in the CLI. The deterministic
    catalog extraction and a rule-based selection fallback work regardless.
    """
    try:
        eng = engine()
    except Exception as exc:  # noqa: BLE001 — unresolved engine -> AI stage off
        logger.debug("smart-layout unavailable: engine did not resolve: %s", exc)
        return False
    # Both models are required, not either/or: select_layouts() needs the LLM
    # and build_catalog()/visual_confirm() need the VLM, and offering
    # --smart-layout with only one resolved would fail midway through a run.
    return bool(eng.get("llm", {}).get("model")) and bool(eng.get("vlm", {}).get("model"))


# ── catalog: deterministic geometry + optional VLM captions ─────────────────
_CAPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "archetype": {"type": "string", "enum": list(ARCHETYPES)},
        "background": {"type": "string"},
        "is_content_layout": {"type": "boolean"},
        "one_line": {"type": "string"},
    },
    "required": ["archetype", "is_content_layout", "one_line"],
}

_CAPTION_PROMPT = (
    "These images are DIFFERENT slides that all use the SAME PowerPoint "
    "template layout, only the placeholder content differs. Describe the "
    "REUSABLE layout, NOT the specific words or pictures:\n"
    "- archetype: its role, one of: " + ", ".join(ARCHETYPES) + ". Use "
    "'reference-non-content' for a brand reference page (colour palette, logo "
    "sheet, icon grid) that is NOT meant to hold authored content.\n"
    "- background: white / black / green / gradient / photo (one word/phrase).\n"
    "- is_content_layout: false ONLY for brand-reference pages.\n"
    "- one_line: a single sentence a picker can match a slide against.\n"
    "Reply as JSON."
)


def build_catalog(
    template: Path,
    *,
    chat: ChatFn | None = None,
    render: RenderFn | None = None,
    use_vision: bool = True,
    cache_path: Path | None = None,
    refresh: bool = False,
) -> list[LayoutInfo]:
    """Build the full layout catalog for *template*: geometry + (optional) captions.

    Parameters
    ----------
    template : Path
        The designer PPTX template to catalog.
    chat : ChatFn, optional
        Vision transport for captioning; defaults to the real engine-backed
        one. Ignored when *use_vision* is ``False``.
    render : RenderFn, optional
        Template-page renderer; defaults to the real LibreOffice+poppler one.
    use_vision : bool, default True
        When ``False`` (or when rendering/chat is unavailable), every layout
        gets a rule-based caption instead of a VLM one — the catalog still
        builds, just without visual captions.
    cache_path : Path, optional
        Where to persist/read the catalog JSON. Defaults to a content-hashed
        path under md2star's cache dir, so re-running on the same template is
        free.
    refresh : bool, default False
        Force a rebuild even if a cache file exists.

    Returns
    -------
    list[LayoutInfo]
        One entry per distinct designer layout name.
    """
    if cache_path is None:
        # Content-hashed, not path-hashed: two callers pointing at the same
        # template bytes (e.g. a shared brand asset referenced from different
        # project dirs) share one cached catalog instead of rebuilding it.
        cache_path = cache_dir("pptx_layout") / f"{osh.hashfile(str(template))}.json"
    if cache_path.exists() and not refresh:
        try:
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
            return [
                LayoutInfo(
                    **{**item, "placeholders": [Placeholder(**p) for p in item["placeholders"]]}
                )
                for item in raw
            ]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            # A corrupt or schema-mismatched cache file (e.g. from an older
            # md2star version) should never break the build — just rebuild.
            logger.debug("pptx layout cache unreadable, rebuilding: %s", exc)

    catalog = extract_layouts(template)
    if use_vision:
        render = render or default_render()
        chat = chat or default_chat(kind="vlm")
        for info in catalog:
            # Nothing to caption for a reference page (never offered to the
            # selector anyway) or a layout with no rendered example.
            if not info.is_content_layout or not info.example_pages:
                continue
            # Up to 3 examples, per the PoC's own finding: captioning from
            # several instances describes the *reusable* layout instead of
            # one example's filler content, and more than 3 rarely changes
            # the caption while tripling the upload cost.
            images = [render(template, p) for p in info.example_pages[:3]]
            images = [img for img in images if img]
            if not images:
                continue  # render unavailable (no soffice/pdftoppm) -> skip
            out = chat(_CAPTION_PROMPT, images, _CAPTION_SCHEMA)
            data = (
                out
                if isinstance(out, dict)
                else (json.loads(out) if isinstance(out, str) else None)
            )
            if not data:
                continue  # transport failure or unparseable reply -> keep the rule-based defaults
            info.archetype = data.get("archetype", info.archetype)
            info.background = str(data.get("background", "")).strip()
            info.caption = str(data.get("one_line", "")).strip()
            # The VLM can override the name-based reference-page heuristic
            # (extract_layouts) with an actual look at the rendered slide —
            # more reliable for oddly-named layouts.
            info.is_content_layout = bool(data.get("is_content_layout", info.is_content_layout))

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps([_layout_info_dict(i) for i in catalog], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return catalog


def _layout_info_dict(info: LayoutInfo) -> dict:
    # asdict() recurses into the nested Placeholder dataclasses too, so the
    # result is plain-JSON-safe in one call, no per-field serialisation.
    return asdict(info)


# ── deck segmentation ────────────────────────────────────────────────────────
_HR_RE = re.compile(r"(?m)^[ \t]*(\*\*\*+|---+|___+)[ \t]*$")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_HEADING_RE = re.compile(r"(?m)^#{1,2}\s+(.*)$")


def _features(body: str) -> list[str]:
    """Detect the structural cues that hint at a layout (regex, no AI)."""
    f: list[str] = []
    if re.search(r"::: *column", body):
        f.append("two-column")
    if re.search(r"!\[.*?\]\(", body):
        f.append("image")
    if re.search(r"^\s*\|.*\|", body, re.MULTILINE):
        f.append("table")
    # mermaid checked BEFORE the generic fence: a ```mermaid block would also
    # match the plain ```-fence regex, and mermaid is the more specific,
    # more useful signal for layout selection (a diagram, not "some code").
    if "```mermaid" in body:
        f.append("mermaid")
    elif re.search(r"^```", body, re.MULTILINE):
        f.append("code")
    if re.search(r"\{\.big\}", body):
        f.append("big-statement")
    # ordered-list before bullets for the same reason: check the more
    # specific pattern first so a slide isn't double-tagged confusingly.
    if re.search(r"^\s*\d+\.\s", body, re.MULTILINE):
        f.append("ordered-list")
    elif re.search(r"^\s*[-*] ", body, re.MULTILINE):
        f.append("bullets")
    if re.search(r"^>\s", body, re.MULTILINE):
        f.append("quote")
    return f


def _slide_from_chunk(index: int, chunk: str) -> Slide | None:
    visible = _HTML_COMMENT_RE.sub("", chunk).strip()
    if not visible:
        return None
    m = _HEADING_RE.search(visible)
    title = re.sub(r"\s*\{\.[^}]*\}\s*$", "", m.group(1)).strip() if m else "(untitled)"
    return Slide(index=index, title=title, body=visible, features=_features(visible))


def segment(markdown: str) -> list[Slide]:
    """Split *markdown* into slides.

    Prefers explicit horizontal-rule slide breaks (``***`` / ``---`` / ``___``
    on their own line, the common reveal.js/Marp/this-project convention);
    when the document has none, falls back to splitting on every H1/H2
    heading, mirroring Pandoc's own default slide-level behaviour.
    """
    chunks = _HR_RE.split(markdown)
    # re.split with a capturing group also yields the separators; drop them.
    chunks = [
        c
        for c in chunks
        if c not in ("***", "---", "___") and not re.fullmatch(r"\*+|-+|_+", c or "")
    ]
    if len(chunks) <= 1:
        # <=1 chunk means the HR split found no separators at all (a single
        # leftover chunk is just the whole document) — fall back to headings.
        # Reconstruct chunks by splitting on each heading line's start offset.
        starts = [m.start() for m in _HEADING_RE.finditer(markdown)]
        if len(starts) > 1:
            chunks = [
                markdown[a:b] for a, b in zip(starts, starts[1:] + [len(markdown)], strict=True)
            ]
        else:
            chunks = [markdown]
    slides: list[Slide] = []
    for chunk in chunks:
        s = _slide_from_chunk(len(slides) + 1, chunk)
        if s is not None:
            slides.append(s)
    return slides


# ── stage A: LLM text-based selection ────────────────────────────────────────
_SELECT_SCHEMA = {
    "type": "object",
    "properties": {
        "choices": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "layout_name": {"type": "string"},
                    "confidence": {"type": "number"},
                    "why": {"type": "string"},
                },
                "required": ["index", "layout_name", "why"],
            },
        }
    },
    "required": ["choices"],
}

_SELECT_PROMPT_HEADER = (
    "You map Markdown slides onto a designer's PowerPoint template. For EACH "
    "Markdown slide, choose the ONE template layout whose design best carries "
    "its role. Match by ARCHETYPE:\n"
    "- a lone title / the deck opener -> cover\n"
    "- a part/section header ('Part N ...', or a {.big} heading with little "
    "body) -> section-divider\n"
    "- a short punchy one-liner ({.big}) -> big-statement\n"
    "- a slide whose whole point is one figure/percentage -> big-number\n"
    "- two-column content -> two-column-split\n"
    "- an image-dominant slide (one figure/screenshot) -> photo-hero\n"
    "- an ordered list of steps -> process-steps\n"
    "- normal bullet/paragraph content -> bulleted-content\n"
    "- the final thanks/closing slide -> closing\n"
    "Prefer VARIETY: do not send most slides to one generic layout. Reserve "
    "cover/closing/section-divider for those roles.\n\n"
)


def _catalog_block(content: list[LayoutInfo]) -> str:
    return "\n".join(f"- {c.name} [{c.archetype}] {c.caption}".rstrip() for c in content)


def _archetype_fallback(features: list[str]) -> str:
    """A cheap rule-based archetype guess, used when the LLM stage is unusable."""
    if "big-statement" in features:
        return "big-statement"
    if "mermaid" in features or "image" in features:
        return "photo-hero"
    if "ordered-list" in features:
        return "process-steps"
    if "two-column" in features:
        return "two-column-split"
    return "bulleted-content"


def select_layouts(
    slides: list[Slide],
    catalog: list[LayoutInfo],
    *,
    chat: ChatFn | None = None,
    batch: int = 12,
) -> None:
    """Fill ``slide.chosen_layout`` for every slide via batched LLM text calls.

    Only *content* layouts are offered (brand-reference pages are dropped),
    each tagged with its archetype so the model matches by role. On any
    transport failure, slides in that batch fall back to the best
    archetype-matching content layout (never left unassigned).
    """
    content = [c for c in catalog if c.is_content_layout]
    if not content:
        return
    # First-seen wins per archetype: catalog order runs most-used layout
    # first (see extract_layouts' final sort), so this favours the
    # template's more common/representative layout for each role.
    by_archetype: dict[str, str] = {}
    for c in content:
        by_archetype.setdefault(c.archetype, c.name)
    names = {c.name for c in content}
    fallback = by_archetype.get("bulleted-content", content[0].name)
    cat_txt = _catalog_block(content)
    chat = chat or default_chat(kind="llm")

    # Batched, not one call per slide: keeps the prompt (and cost) bounded for
    # a long deck while still giving the model several slides' worth of
    # context at once to reason about variety across the batch.
    for start in range(0, len(slides), batch):
        group = slides[start : start + batch]
        listing = "\n".join(
            f"[{s.index}] title: {s.title!r} | features: {', '.join(s.features) or 'plain text'}"
            for s in group
        )
        prompt = (
            f"{_SELECT_PROMPT_HEADER}TEMPLATE LAYOUT CATALOG (content layouts only):\n{cat_txt}\n\n"
            f"MARKDOWN SLIDES:\n{listing}\n\n"
            'Reply as JSON {"choices":[{index, layout_name, confidence, why}]} '
            "with one entry per slide. layout_name MUST be one of the catalog "
            "names; why <= 12 words."
        )
        out = chat(prompt, None, _SELECT_SCHEMA)
        try:
            data = (
                out if isinstance(out, dict) else (json.loads(out) if isinstance(out, str) else {})
            )
            choices = data.get("choices", [])
        except (json.JSONDecodeError, AttributeError):
            # A transport failure (None) or a malformed reply both land here;
            # an empty choices list means every slide in this batch falls
            # through to the archetype-fallback branch below.
            choices = []
        by_index = {c.get("index"): c for c in choices}
        for s in group:
            c = by_index.get(s.index) or {}
            # Reject a hallucinated layout name outright — better a sensible
            # archetype fallback than a KeyError deep in the assembler later.
            name = c.get("layout_name") if c.get("layout_name") in names else None
            if name is None:
                name = by_archetype.get(_archetype_fallback(s.features), fallback)
            s.chosen_layout = name
            s.chosen_confidence = c.get("confidence")
            s.chosen_why = c.get("why", "") or ""


# ── stage B: VLM visual tie-break ────────────────────────────────────────────
_VISUAL_SCHEMA = {
    "type": "object",
    "properties": {
        "best": {"type": "string"},
        "why": {"type": "string"},
    },
    "required": ["best"],
}

_VISUAL_PROMPT = (
    "You are choosing which PowerPoint template layout will best PRESENT the "
    "following slide content (shown below as text). Each image below is one "
    "candidate layout, in this order: {names}. Look at where each candidate "
    "places its title/body/image regions and judge which one actually suits "
    "this content best, not just which name sounds right.\n\n"
    "SLIDE:\ntitle: {title!r}\nfeatures: {features}\n\n"
    'Reply as JSON {{"best": <one of {names}>, "why": <<=12 words>}}.'
)


def _alternates_for(s: Slide, catalog_by_name: dict[str, LayoutInfo], k: int) -> list[LayoutInfo]:
    """Pick up to *k* candidate layouts for the visual tie-break: the current
    pick plus archetype-diverse alternates (so the VLM sees a real choice, not
    near-duplicates)."""
    chosen = catalog_by_name.get(s.chosen_layout) if s.chosen_layout else None
    # Only layouts with a rendered example are eligible: without one there is
    # no thumbnail to show the vision model, so it could never be picked.
    pool = [c for c in catalog_by_name.values() if c.is_content_layout and c.example_pages]
    out: list[LayoutInfo] = [chosen] if chosen else []
    seen_archetypes = {chosen.archetype} if chosen else set()
    for c in pool:
        if len(out) >= k:
            break
        if c.name in {o.name for o in out}:
            continue
        # One layout per archetype: two "bulleted-content" layouts would look
        # nearly identical in a thumbnail comparison and waste a slot that
        # could show a genuinely different composition instead.
        if c.archetype in seen_archetypes:
            continue
        out.append(c)
        seen_archetypes.add(c.archetype)
    return out


def visual_confirm(
    slides: list[Slide],
    catalog: list[LayoutInfo],
    *,
    chat: ChatFn | None = None,
    render: RenderFn | None = None,
    template: Path | None = None,
    k: int = 3,
    only_low_confidence: bool = False,
    confidence_threshold: float = 0.7,
) -> None:
    """Visually confirm (or override) each slide's text-stage layout pick.

    This is the VLM dimension the pure-text :func:`select_layouts` cannot
    provide: it renders each candidate's example page, shows the vision model
    the actual thumbnails side by side with the slide's content, and asks
    which one genuinely carries that content best. Disagreements override
    ``slide.chosen_layout``; any transport/render failure leaves the text
    stage's pick untouched (best-effort, never load-bearing).

    Parameters
    ----------
    only_low_confidence : bool, default False
        When ``True``, only re-check slides whose text-stage confidence is
        missing or below *confidence_threshold* (cheaper, fewer VLM calls);
        when ``False`` (default) every slide gets a visual check.
    """
    if template is None:
        return
    render = render or default_render()
    chat = chat or default_chat(kind="vlm")
    catalog_by_name = {c.name: c for c in catalog}

    for s in slides:
        if only_low_confidence:
            conf = s.chosen_confidence
            # A missing confidence (transport failure -> archetype fallback)
            # is treated as "worth checking", not skipped — it's exactly the
            # case where the text stage had the least signal to go on.
            if conf is not None and conf >= confidence_threshold:
                continue
        candidates = _alternates_for(s, catalog_by_name, k)
        if len(candidates) < 2:
            continue  # nothing to tie-break against
        images: list[bytes] = []
        usable: list[LayoutInfo] = []
        for c in candidates:
            page = c.rep_page
            if page is None:
                continue
            png = render(template, page)
            if png is None:
                continue
            # images/usable stay index-aligned: the prompt's "in this order"
            # listing must match exactly what the model is shown.
            images.append(png)
            usable.append(c)
        if len(usable) < 2:
            continue  # a render/no-example gap left too few options to compare
        names = [c.name for c in usable]
        prompt = _VISUAL_PROMPT.format(
            names=", ".join(names),
            title=s.title,
            features=", ".join(s.features) or "plain text",
        )
        out = chat(prompt, images, _VISUAL_SCHEMA)
        data = out if isinstance(out, dict) else (json.loads(out) if isinstance(out, str) else None)
        if not data:
            continue
        best = data.get("best")
        if best in names and best != s.chosen_layout:
            logger.info(
                "visual tie-break overrides slide %d: %s -> %s (%s)",
                s.index,
                s.chosen_layout,
                best,
                data.get("why", ""),
            )
            s.chosen_layout = best
            s.chosen_why = str(data.get("why", "")) or s.chosen_why
