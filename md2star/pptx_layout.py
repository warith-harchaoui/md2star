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
import os
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

from md2star import pptx_fit

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

#: Placeholder kinds PowerPoint fills itself, so they describe no content
#: region (mirrors :data:`md2star.pptx_assemble.LATENT_KINDS`, which owns the
#: vocabulary; spelled here because this module must not import the assembler).
_LATENT_KINDS = frozenset({"dt", "ftr", "sldNum"})


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
    #: Speaker notes authored for this slide — the content of a Pandoc
    #: ``::: notes`` fenced div, held *off* ``body`` on purpose. Notes are the
    #: presenter's private script: anything left in ``body`` is drawn on the
    #: slide, where the audience reads it. The assembler puts this in the
    #: notes pane instead (:func:`md2star.pptx_assemble.assemble`).
    notes: str = ""
    features: list[str] = field(default_factory=list)
    chosen_layout: str | None = None
    chosen_confidence: float | None = None
    chosen_why: str = ""
    # Bounded per-slide adjustments the target-matching eyeball loop
    # (:mod:`md2star.pptx_assemble`) writes back after judging a render against
    # the chosen layout's thumbnail: font_delta (pt, title/body), bullets (max
    # bullet count), img_grow (fractional image box growth). Empty = no change.
    #: A cover (slide 1) or a closing (slide n) carries its title and nothing
    #: else, whatever markup the source happens to have under it. Set by
    #: :func:`segment` so every stage agrees on it: the assembler enforces it,
    #: the fit model measures it as the big statement it is, and the visual
    #: tie-break is told what the slide actually contains. A hand-built
    #: ``Slide`` is taken at its word.
    title_only: bool = False
    overrides: dict = field(default_factory=dict)
    #: Measured content (:func:`md2star.pptx_fit.measure`), filled by
    #: :func:`select_layouts`. Kept on the slide so the visual stage and the
    #: assembler can reason about quantities instead of re-deriving them.
    metrics: object | None = None
    #: Layouts ranked by geometric fit, best first, as
    #: ``[(LayoutInfo, FitReport), ...]``. Also filled by `select_layouts`.
    fit_ranked: list = field(default_factory=list)
    #: Layouts the eyeball loop has already moved this slide off, so a later
    #: pass does not send it back somewhere the vision model already rejected.
    tried_layouts: list[str] = field(default_factory=list)
    #: Heading level that opened the slide: 1 for ``#``, 2 for ``##``, 0 for
    #: a slide with no heading. An ``#`` past the cover opens a new part of
    #: the deck, which is a section divider, not another content slide.
    level: int = 0
    #: ``{layout="Big Number"}`` on the heading: the exact template layout
    #: the author asked for. Bypasses every model when the template has it.
    layout_hint: str | None = None
    #: A role asked for by class (``{.statement}``, ``{.recap}``, ...), or
    #: implied by the title ("Key takeaways"); see :data:`CLASS_HINTS`.
    class_hint: str | None = None
    #: The one or two lines under a cover's / divider's title: its prose, or
    #: for the cover the front matter's ``subtitle`` / ``author`` / ``date``.
    #: Placed on the layout's subtitle zone so a title-only slide keeps them.
    subtitle: str = ""
    #: Set when the layout was decided by an explicit hint rather than chosen:
    #: no model, tie-break or reselection moves a pinned slide.
    pinned: bool = False
    #: The deck's ``lang`` (front matter), for the "(suite)" / "(cont.)" label
    #: of a continuation slide.
    lang: str = ""


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


def slide_size(template: Path) -> tuple[int, int] | None:
    """The deck's canvas in EMU, from ``ppt/presentation.xml``'s ``<p:sldSz>``.

    Needed by the compositional checks in :mod:`md2star.pptx_fit`: "is this
    layout balanced?" and "does the focal element sit on a third?" are
    questions about where a box falls *on the slide*, so they cannot be
    answered from the box alone.

    Returns ``None`` when the part is missing or unparseable, which every
    caller treats as "skip the compositional checks" rather than as an error.
    """
    try:
        with zipfile.ZipFile(template) as z:
            root = ET.fromstring(z.read("ppt/presentation.xml"))
    except (KeyError, zipfile.BadZipFile, ET.ParseError, OSError):
        return None
    for el in root.iter():
        if el.tag.endswith("}sldSz"):
            try:
                return int(el.attrib["cx"]), int(el.attrib["cy"])
            except (KeyError, ValueError):
                return None
    return None


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


#: A picture covering at least this share of the canvas on an example page is
#: a content region rather than a logo — same threshold, same reasoning, as
#: :data:`md2star.pptx_clone.CONTENT_PICTURE_AREA`.
_PAGE_PICTURE_AREA = 0.04


def _declared_pt(sp: ET.Element) -> float:
    """Largest run size a shape declares, in points (``0`` when inherited)."""
    sizes = [int(pr.get("sz")) for pr in sp.iter(f"{{{_NS['a']}}}rPr") if pr.get("sz")]
    return max(sizes, default=0) / 100.0


def _shape_text(sp: ET.Element) -> str:
    return "".join(t.text or "" for t in sp.iter(f"{{{_NS['a']}}}t")).strip()


def _page_regions(template: Path, page: int, canvas: tuple[int, int] | None) -> list[Placeholder]:
    """Describe a layout from the page that demonstrates it, not from its XML.

    Why this exists, measured rather than assumed: on the reference designer
    template all 39 layouts type **every** placeholder ``body`` and declare no
    title anywhere — a Google Slides export never marks one — and several
    describe nothing but an eyebrow label while the slide's real display text
    lives on the example page as a free text box. ``title2``'s layout declares
    two boxes 0.33 inch high; its example page sets a 56 pt heading in a box
    the layout has never heard of.

    A capacity model reading those layouts sees the same thing everywhere.
    Observed consequence: every layout scored identically, so the geometric
    ranking could not discriminate at all, a one-line cover was as good a fit
    as a two-column content design, and the choice fell through to whatever
    the vision model happened to like.

    So where the template demonstrates a layout, the demonstration is what gets
    measured: the biggest declared type is the title, the remaining text frames
    are body regions, and a picture big enough to be content is a ``pic``
    region. The same reading :func:`md2star.pptx_clone.classify` performs for
    Seam E, done here with ElementTree so this module stays free of the
    optional ``python-pptx`` dependency.

    Returns
    -------
    list of Placeholder
        Empty when the page yields nothing usable, which is the caller's
        signal to keep the layout's own declaration.
    """
    with zipfile.ZipFile(template) as z:
        name = f"ppt/slides/slide{page}.xml"
        if name not in z.namelist():
            return []
        root = ET.fromstring(z.read(name))  # noqa: S314 — trusted local template
    tree = root.find("./p:cSld/p:spTree", _NS)
    if tree is None:
        return []

    canvas_area = max(1, (canvas[0] * canvas[1]) if canvas else 0)
    texts: list[tuple[ET.Element, tuple[int, int, int, int], float]] = []
    pictures: list[tuple[int, int, int, int]] = []
    for sp in tree:
        tag = sp.tag.split("}")[-1]
        if tag not in ("sp", "pic"):
            continue  # a group, a chart, a connector: not a content region
        box = _placeholder_emu(sp)
        if box is None:
            continue  # no explicit geometry on a slide is rare, and unusable
        if tag == "pic":
            if canvas and box[2] * box[3] >= _PAGE_PICTURE_AREA * canvas_area:
                pictures.append(box)
            continue
        if _placeholder_kind(sp) in _LATENT_KINDS or not _shape_text(sp):
            continue  # a date/footer/slide-number, or a shape drawn for its fill
        texts.append((sp, box, _declared_pt(sp)))

    if not texts:
        return []
    # The heading is the biggest type on the page; ties go to whichever sits
    # higher, because on a page where nothing declares a size the top one is
    # still the better guess than the first in XML order.
    title = max(texts, key=lambda row: (row[2], -row[1][1]))
    regions = [Placeholder(idx=0, kind="title", emu=title[1])]
    regions += [
        Placeholder(idx=i, kind="body", emu=box)
        for i, (sp, box, _pt) in enumerate(texts, start=1)
        if sp is not title[0]
    ]
    regions += [
        Placeholder(idx=len(texts) + i, kind="pic", emu=box)
        for i, box in enumerate(pictures, start=1)
    ]
    return regions


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

    Each layout is described from the **example page that demonstrates it**
    when the template has one (:func:`_page_regions`), falling back to the
    layout part's own placeholders otherwise. That is not a refinement but a
    correctness fix: a designer template exported from Google Slides types
    every placeholder ``body`` and sometimes declares nothing but an eyebrow
    label, which makes every layout measure the same and leaves layout
    selection with no signal at all.

    Enumerates every ``ppt/slideLayouts/slideLayoutN.xml`` part directly (not
    only the layouts some slide happens to use) so a template distributed with
    no example slides at all — just its layouts, e.g. python-pptx's own bundled
    default template — still yields a full catalog; ``example_pages`` is simply
    empty for a layout no slide currently demonstrates (no thumbnail/caption
    for it, but its geometry is still extracted and it can still be selected).
    """
    pages = _layout_example_pages(template)
    canvas = slide_size(template)
    infos: list[LayoutInfo] = []
    seen: set[str] = set()
    for layout_part in _all_layout_files(template):
        name = _layout_name(template, layout_part)
        if name in seen:
            continue  # two parts sharing a designer-authored name — keep the first
        seen.add(name)
        placeholders = _layout_placeholders(template, layout_part.rsplit("/", 1)[-1])
        # Where the template demonstrates this layout, the demonstration wins:
        # a designer's own example page describes the layout far better than a
        # layout part that types everything `body` and sometimes describes only
        # an eyebrow. See :func:`_page_regions` for the evidence.
        for page in pages.get(name, []):
            demonstrated = _page_regions(template, page, canvas)
            if demonstrated:
                placeholders = demonstrated
                break
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
        from .pipeline import _find_soffice as _engine_find_soffice  # noqa: PLC0415

        return _engine_find_soffice()
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

    ``MD2STAR_LLM_MODEL`` / ``MD2STAR_VLM_MODEL`` in the environment name the
    model for that kind and override ``llm.engine.yaml``: the resolved default
    (gemma3:12b on the reference machine) approves nearly every slide it is
    shown as a judge, and swapping it should not mean regenerating the engine
    file. An explicit *model* argument still wins over both.
    """
    model = model or os.environ.get(f"MD2STAR_{kind.upper()}_MODEL") or None

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


def parse_json_reply(raw: object) -> dict | None:
    """Recover the JSON object from whatever :data:`ChatFn` actually returned.

    A schema-constrained call *usually* comes back as a ``dict``, and "usually"
    is the whole problem: ``llm.chat`` documents that it hands back the raw
    string when the model does not honour the schema, and on the vision side
    that is the common case rather than the exotic one — the strongest local
    VLMs are precisely the ones Ollama cannot hold to a schema. Those replies
    arrive as the right JSON wrapped in prose or a ``` fence.

    Parsing that with a bare :func:`json.loads` raised
    :class:`json.JSONDecodeError` straight out of whatever stage made the call,
    which turned "this one model reply was chatty" into "the catalog build /
    the tie-break / the whole eyeball loop died". Every one of those stages is
    written to degrade on a bad reply, so the exception was the only thing
    standing between them and the fallback they already had.

    So: a ``dict`` passes through, a string is searched for its first ``{...}``
    span and parsed, and anything unusable is ``None`` — the value every caller
    here already treats as "no answer, use the fallback". Same tolerance
    :func:`md2star.reverse_diagrams._parse_verdict` has always applied to the
    diagram loop's verdicts; this is that stance, shared.

    Parameters
    ----------
    raw : object
        Whatever the transport returned: a parsed ``dict``, a string that may
        or may not be pure JSON, or ``None`` from a failed call.

    Returns
    -------
    dict or None
        The recovered object, or ``None`` when there is nothing usable in it.
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    # Greedy to the last brace on purpose: the verdict/caption object is the
    # outermost one, and a non-greedy match would stop at the first nested
    # object's closing brace and parse a truncated fragment.
    span = re.search(r"\{.*\}", raw, re.DOTALL)
    if span is None:
        return None
    try:
        parsed = json.loads(span.group(0))
    except (json.JSONDecodeError, TypeError):
        return None
    # A model answering with a bare list or number parses fine and is still
    # not a verdict; only an object can carry the keys callers read.
    return parsed if isinstance(parsed, dict) else None


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
    llm_model = os.environ.get("MD2STAR_LLM_MODEL") or eng.get("llm", {}).get("model")
    vlm_model = os.environ.get("MD2STAR_VLM_MODEL") or eng.get("vlm", {}).get("model")
    return bool(llm_model) and bool(vlm_model)


# ── catalog: deterministic geometry + optional VLM captions ─────────────────
#: Bumped whenever what a cached catalog holds changes meaning, so an old
#: cache file is never mistaken for this version's.
CATALOG_VERSION = 2

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
        # Versioned, and keyed by the captioning model when one is forced:
        # captions written by another model, or by an older catalog
        # extractor, are not this run's catalog. `refresh` (the CLI's
        # --refresh-catalog) remains the way to force a rebuild outright.
        vlm = re.sub(r"[^\w.-]+", "_", os.environ.get("MD2STAR_VLM_MODEL", ""))
        key = f"{osh.hashfile(str(template))}-v{CATALOG_VERSION}" + (f"-{vlm}" if vlm else "")
        cache_path = cache_dir("pptx_layout") / f"{key}.json"
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
            data = parse_json_reply(out)
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

#: YAML metadata block, and *only* at the very start of the document — Pandoc's
#: own rule. It has to be removed before anything else looks at the text: its
#: closing ``---`` is indistinguishable from a horizontal rule, so left in
#: place it splits off a leading slide whose bullets are the raw metadata
#: lines ("title: Q3 review", "author: ..."). Both ``---`` and ``...`` close a
#: Pandoc metadata block.
_FRONT_MATTER_RE = re.compile(
    r"\A\ufeff?---[ \t]*\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.DOTALL
)

#: One scalar ``key: value`` line of that block. Nested/sequence YAML is left
#: alone — the only keys this module wants are the flat title-ish ones, and
#: guessing at the rest without a YAML parser would be worse than ignoring it.
_META_LINE_RE = re.compile(r"(?m)^([A-Za-z][\w-]*)[ \t]*:[ \t]*(.+?)[ \t]*$")

#: What the first non-blank line of a metadata block has to look like. Without
#: this, a deck that *opens* with a horizontal-rule slide break — ``---`` on
#: line 1, then the first slide — would have that slide eaten as metadata, and
#: a `key:` with a nested value under it still has to count, so this tests the
#: shape of the line rather than reusing the scalar pattern above.
_YAML_KEY_RE = re.compile(r"\A[A-Za-z][\w-]*[ \t]*:")

#: A Pandoc ``notes`` fenced div: ``::: notes`` / ``:::: {.notes}`` … ``:::``.
#: Captured rather than merely skipped, because the text inside it is the one
#: part of a slide that must NOT be drawn on the slide.
_NOTES_RE = re.compile(
    r"(?ms)^:{3,}[ \t]*(?:notes\b|\{[^}]*\.notes[^}]*\})[^\n]*\n(.*?)^:{3,}[ \t]*$\n?"
)


#: A column div: ``::: {.column}`` / ``::: column`` (never the ``.columns``
#: wrapper around them). Pandoc's own two-column markup.
_COLUMN_OPEN_RE = re.compile(r"^:{3,}[ \t]*(?:\{[^}]*\.column\b(?!s)[^}]*\}|column\b(?!s))")
_DIV_OPEN_RE = re.compile(r"^:{3,}[ \t]*\S")
_DIV_CLOSE_RE = re.compile(r"^:{3,}[ \t]*$")

#: Code fences, whose ``# comment`` lines and ``---`` lines are not slide
#: structure. Both fence characters, any length of three or more.
_FENCE_SPAN_RE = re.compile(r"(?ms)^[ \t]*(```+|~~~+)[^\n]*\n.*?^[ \t]*\1[ \t]*$")
_SLIDE_HEADING_RE = re.compile(r"(?m)^(#{1,2})[ \t]+(.*?)[ \t]*$")
_ATTR_TAIL_RE = re.compile(r"\s*\{([^{}]*)\}\s*$")
_LAYOUT_ATTR_RE = re.compile(r"""\blayout\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"']+))""")

#: What a ``{.class}`` on a slide heading asks for: an archetype, and the
#: layout names that mean it in a template that names its layouts plainly
#: (PowerPoint's own vocabulary, and the course template's). The name wins
#: when the template has it; the archetype is the fallback.
CLASS_HINTS: dict[str, tuple[str | None, tuple[str, ...]]] = {
    "statement": ("big-statement", ("Statement",)),
    "big": ("big-statement", ("Statement",)),
    "bignumber": ("big-number", ("Big Number",)),
    "big-number": ("big-number", ("Big Number",)),
    "quote": ("quote", ("Quote",)),
    "recap": (None, ("Recap",)),
    "agenda": (None, ("Agenda",)),
    "section": ("section-divider", ("Section Header", "Section")),
    "closing": ("closing", ("Closing",)),
    "cover": ("cover", ("Title Slide",)),
}

#: A slide that closes a sequence by restating it: mapped to a template's
#: "Recap" layout when it has one. French and English, the course's two.
_RECAP_TITLE_RE = re.compile(
    r"^\s*(?:qu['’]est[- ]ce que nous avons appris|ce que nous avons appris"
    r"|what we(?: have|'ve)? learn(?:ed|t)|key takeaways?)\s*[?!.:]*\s*$",
    re.IGNORECASE,
)


def _features(body: str) -> list[str]:
    """Detect the structural cues that hint at a layout (regex, no AI)."""
    f: list[str] = []
    if re.search(r"(?m)^:{3,}[ \t]*(?:\{[^}]*\.columns?\b|columns?\b)", body):
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


def split_front_matter(markdown: str) -> tuple[str, dict[str, str]]:
    """Separate a leading YAML metadata block from the deck body.

    Parameters
    ----------
    markdown : str
        The whole authored document.

    Returns
    -------
    tuple of (str, dict)
        The document with any leading metadata block removed, and the flat
        scalar ``key: value`` pairs it declared (lower-cased keys; empty when
        there was no block).

    Examples
    --------
    >>> body, meta = split_front_matter("---\\ntitle: Q3\\n---\\n\\n# Q3\\n")
    >>> meta["title"], body.strip()
    ('Q3', '# Q3')

    A deck that merely *opens* with a slide break keeps every slide:

    >>> split_front_matter("---\\n\\n# First\\n\\n---\\n\\n# Second\\n")[0].lstrip()
    '# First\\n\\n---\\n\\n# Second\\n'
    """
    m = _FRONT_MATTER_RE.match(markdown)
    if m is None:
        return markdown, {}
    block = m.group(1)
    # Two delimiters that look alike: `---` opens a metadata block, and `---`
    # on its own line is also the slide separator this module splits on. Only
    # the content tells them apart, so a block whose first real line is not a
    # YAML key is a slide, and consuming it would silently delete it.
    first = next((line for line in block.splitlines() if line.strip()), "")
    if not _YAML_KEY_RE.match(first.strip()):
        return markdown, {}
    meta = {k.lower(): v for k, v in _META_LINE_RE.findall(block)}
    return markdown[m.end() :], meta


def split_notes(chunk: str) -> tuple[str, str]:
    """Separate a slide's visible content from its speaker notes.

    Parameters
    ----------
    chunk : str
        One slide's Markdown, notes div included.

    Returns
    -------
    tuple of (str, str)
        The content to draw on the slide, and the notes to put in the notes
        pane (several ``::: notes`` divs on one slide are joined).

    Examples
    --------
    >>> body, notes = split_notes("## T\\n\\n::: notes\\nsay this\\n:::\\n")
    >>> notes
    'say this'
    >>> "say this" in body
    False
    """
    taken: list[str] = []

    def _take(m: re.Match[str]) -> str:
        taken.append(m.group(1).strip())
        return "\n"

    visible = _NOTES_RE.sub(_take, chunk)
    return visible, "\n\n".join(n for n in taken if n)


def _protected_spans(text: str) -> list[tuple[int, int]]:
    """Character spans whose lines are content, never slide structure.

    A ``# comment`` in a Python fence is not a heading and a ``---`` in a YAML
    fence is not a slide break; neither is anything in a speaker-notes div.
    """
    spans = [m.span() for m in _FENCE_SPAN_RE.finditer(text)]
    spans += [m.span() for m in _NOTES_RE.finditer(text)]
    return spans


def _inside(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(a <= pos < b for a, b in spans)


def _chunks(markdown: str) -> list[str]:
    """Cut a deck into slide-sized chunks, the way Pandoc does.

    Every horizontal rule ends a slide and every ``#`` / ``##`` heading starts
    one — both, always. This used to be either/or: a single stray ``---``
    anywhere switched the whole deck to rule-splitting, and every heading
    after it was folded into whichever slide came before. A heading never
    splits off the text that precedes it within a chunk when that text has
    no heading of its own (an image above the title stays with its slide).
    """
    spans = _protected_spans(markdown)
    events: list[tuple[int, int, str]] = []
    for m in _HR_RE.finditer(markdown):
        if not _inside(m.start(), spans):
            events.append((m.start(), m.end(), "hr"))
    for m in _SLIDE_HEADING_RE.finditer(markdown):
        if not _inside(m.start(), spans):
            events.append((m.start(), m.start(), "h"))
    events.sort()
    chunks: list[str] = []
    start, has_heading = 0, False
    for pos, end, kind in events:
        if kind == "hr":
            chunks.append(markdown[start:pos])
            start, has_heading = end, False
        else:
            # Before the chunk's first heading, only a notes div (the script
            # of the slide that just ended, written after its `---`) is cut
            # off as a chunk of its own, so it goes back to that slide.
            lead = markdown[start:pos]
            notes_only = lead.strip() and not split_notes(_HTML_COMMENT_RE.sub("", lead))[0].strip()
            if has_heading or notes_only:
                chunks.append(lead)
                start = pos
            has_heading = True
    chunks.append(markdown[start:])
    return [c for c in chunks if c.strip()]


def parse_heading(line: str) -> tuple[str, list[str], str | None]:
    """Split a heading's text from its ``{...}`` attributes.

    Returns
    -------
    tuple of (str, list of str, str or None)
        The title, its classes (without the dot), and a ``layout="..."``
        attribute when one is given.

    Examples
    --------
    >>> parse_heading('Growth {.bignumber layout="Big Number"}')
    ('Growth', ['bignumber'], 'Big Number')
    """
    m = _ATTR_TAIL_RE.search(line)
    if m is None:
        return line.strip(), [], None
    attrs = m.group(1)
    classes = re.findall(r"(?<![\w-])\.([\w-]+)", attrs)
    lay = _LAYOUT_ATTR_RE.search(attrs)
    layout = next((g for g in lay.groups() if g), None) if lay else None
    return line[: m.start()].strip(), classes, layout


def _slide_from_chunk(
    index: int, chunk: str, *, default_title: str = ""
) -> tuple[Slide | None, str]:
    """One chunk -> its slide, plus its notes (also when there is no slide).

    A chunk that is *only* notes yields ``(None, notes)``: the caller hangs
    them on the previous slide instead of losing them, which is what used to
    happen to a ``::: notes`` written after a slide's closing ``---``.
    """
    visible, notes = split_notes(_HTML_COMMENT_RE.sub("", chunk))
    visible = visible.strip()
    if not visible:
        return None, notes
    spans = _protected_spans(visible)
    m = next(
        (h for h in _SLIDE_HEADING_RE.finditer(visible) if not _inside(h.start(), spans)), None
    )
    title, classes, layout = parse_heading(m.group(2)) if m else ("", [], None)
    level = len(m.group(1)) if m else 0
    class_hint = next((c.lower() for c in classes if c.lower() in CLASS_HINTS), None)
    if class_hint is None and _RECAP_TITLE_RE.match(title):
        class_hint = "recap"
    slide = Slide(
        index=index,
        # Front-matter `title:` beats "(untitled)" for a deck whose cover is
        # declared as metadata rather than as an H1 — the Pandoc idiom.
        title=title or default_title or "(untitled)",
        body=visible,
        notes=notes,
        features=_features(visible),
        level=level,
        layout_hint=layout,
        class_hint=class_hint,
    )
    return slide, notes


#: Features that are something to *place*: a slide carrying one of these is
#: a content slide wherever it sits in the deck, cover and closing included.
_PAYLOAD = frozenset(
    {"bullets", "ordered-list", "table", "image", "mermaid", "code", "two-column", "quote"}
)


def _prose(body: str) -> str:
    """A title-only slide's own lines of text (its subtitle), markup removed."""
    lines = []
    for raw in body.splitlines():
        s = raw.strip()
        if not s or s.startswith(("#", ":::", "|", "![")):
            continue
        s = re.sub(r"\s*\{[^{}]*\}\s*$", "", s)
        s = re.sub(r"\*\*|__|`", "", s).strip()
        if s:
            lines.append(s)
    return "\n".join(lines)


_BIG_NUMBER_LINE_RE = re.compile(r"(?m)^\s*\*\*([^*\n]{1,12})\*\*\s*$")


def _inferred_class(s: Slide) -> str | None:
    """The role a slide's *form* states, per the course grammar.

    Only unambiguous forms: a short bold figure alone on its line
    (``**×18**``) is a big number; a blockquote with no list is a quote; a
    single short sentence and nothing else is a statement. Anything less clear
    is left to the selection stages.
    """
    feats = set(s.features)
    if feats & {"bullets", "ordered-list", "table", "image", "mermaid", "code", "two-column"}:
        return None
    big = _BIG_NUMBER_LINE_RE.search(s.body)
    if big and re.search(r"\d", big.group(1)):
        return "bignumber"
    if "quote" in feats:
        return "quote"
    prose = _prose(s.body)
    if prose and "\n" not in prose and len(prose) <= 140:
        return "statement"
    return None


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def segment(markdown: str) -> list[Slide]:
    """Split *markdown* into slides.

    Every horizontal rule (``***`` / ``---`` / ``___`` on its own line) ends a
    slide and every ``#`` / ``##`` heading starts one, as in Pandoc (see
    :func:`_chunks`). A leading YAML metadata block is removed first (its
    closing ``---`` is a horizontal rule to every regex here), and each
    slide's ``::: notes`` div is lifted off its body into :attr:`Slide.notes`
    — a chunk holding only notes gives them to the slide before it.

    Nothing is dropped on the way:

    * the cover (and the closing) are title-only **only** when they carry
      nothing to place; their prose becomes :attr:`Slide.subtitle`, and the
      cover's subtitle falls back to the front matter's ``subtitle``,
      ``author`` and ``date``;
    * a front-matter ``title`` that no slide carries becomes a cover of its
      own, as Pandoc's title slide does;
    * an ``#`` heading past the cover with nothing to place is a section
      divider (:attr:`Slide.class_hint` ``"section"``).
    """
    markdown, meta = split_front_matter(markdown)
    lang = meta.get("lang", "")
    slides: list[Slide] = []
    pending_notes: list[str] = []
    for chunk in _chunks(markdown):
        # Only the cover can inherit the metadata title: slide 2 onward has its
        # own heading, and a document-level title repeated there would be wrong.
        s, notes = _slide_from_chunk(
            len(slides) + 1, chunk, default_title=meta.get("title", "") if not slides else ""
        )
        if s is None:
            if not notes:
                continue
            if slides:
                slides[-1].notes = "\n\n".join(n for n in (slides[-1].notes, notes) if n)
            else:
                pending_notes.append(notes)
            continue
        if pending_notes:
            s.notes = "\n\n".join([*pending_notes, s.notes] if s.notes else pending_notes)
            pending_notes = []
        s.lang = lang
        slides.append(s)

    meta_title = meta.get("title", "").strip().strip("'\"")
    cover_lines = [meta.get(k, "").strip().strip("'\"") for k in ("subtitle", "author", "date")]
    cover_lines = [line for line in cover_lines if line]
    if meta_title and (not slides or _norm(slides[0].title) != _norm(meta_title)):
        slides.insert(0, Slide(index=0, title=meta_title, level=1, lang=lang))

    for i, s in enumerate(slides, start=1):
        s.index = i
    if slides:
        n = len(slides)
        for s in slides:
            payload = bool(_PAYLOAD & set(s.features))
            edge = s.index in (1, n)
            divider = s.level == 1 and s.index != 1 and not payload
            if (edge or divider) and not payload:
                # The one place this rule is written down, so the fit model,
                # the tie-break and the assembler all decide about the same
                # slide: a heading, and its subtitle, nothing else.
                s.title_only = True
                s.subtitle = _prose(s.body)
            if s.class_hint is None and s.layout_hint is None and s.title_only:
                # A title-only cover, closing or divider has a role, and a
                # template that names it ("Title Slide", "Closing", "Section
                # Header") gets it without a model guessing.
                if s.index == 1:
                    s.class_hint = "cover"
                elif s.index == n:
                    s.class_hint = "closing"
                elif divider:
                    s.class_hint = "section"
            if s.class_hint is None and s.layout_hint is None and not s.title_only:
                s.class_hint = _inferred_class(s)
        first = slides[0]
        if first.title_only and cover_lines:
            known = {_norm(line) for line in first.subtitle.splitlines()}
            extra = [line for line in cover_lines if _norm(line) not in known]
            first.subtitle = "\n".join(x for x in (first.subtitle, *extra) if x)
    return slides


def continuation_label(lang: str = "", sample: str = "") -> str:
    """``"(suite)"`` for a French deck, ``"(cont.)"`` otherwise.

    The deck's ``lang`` decides when it has one; failing that, a count of
    the commonest French and English function words in *sample* does.
    """
    code = (lang or "").lower()[:2]
    if code:
        return "(suite)" if code == "fr" else "(cont.)"
    words = re.findall(r"[a-zà-ÿ']+", sample.lower())
    fr = sum(
        w
        in {
            "le",
            "la",
            "les",
            "des",
            "est",
            "un",
            "une",
            "de",
            "du",
            "et",
            "pour",
            "que",
            "à",
            "en",
        }
        for w in words
    )
    en = sum(
        w in {"the", "and", "is", "of", "to", "for", "that", "with", "are", "a"} for w in words
    )
    return "(suite)" if fr > en else "(cont.)"


def _body_blocks(body: str) -> tuple[str, list[str]]:
    """A slide body as its heading line plus top-level blocks of Markdown.

    A block is a list item with everything indented under it, or a paragraph.
    Splitting between blocks never cuts a sentence or orphans a sub-bullet.
    """
    lines = body.splitlines()
    heading = ""
    spans = _protected_spans(body)
    offset = 0
    rest: list[str] = []
    for line in lines:
        if not heading and _SLIDE_HEADING_RE.match(line) and not _inside(offset, spans):
            heading = line
        else:
            rest.append(line)
        offset += len(line) + 1
    blocks: list[list[str]] = []
    for line in rest:
        is_item = re.match(r"^(?:[-*+]|\d+[.)])\s+", line)
        if not line.strip():
            if blocks and blocks[-1] and blocks[-1][-1].strip():
                blocks[-1].append("")
            continue
        indented = line[:1] in (" ", "\t")
        if is_item or not blocks or (not indented and not blocks[-1][-1].strip()):
            blocks.append([line])
        else:
            blocks[-1].append(line)
    return heading, ["\n".join(b).strip() for b in blocks if "\n".join(b).strip()]


def split_slide(s: Slide, groups: list[list[str]], heading: str, label: str) -> list[Slide]:
    """Rebuild *s* as one slide per group of blocks, continuations labelled."""
    out: list[Slide] = []
    for k, blocks in enumerate(groups):
        title = s.title if k == 0 else f"{s.title} {label}"
        head = heading if k == 0 else f"## {title}"
        body = "\n\n".join([head, *blocks]) if head else "\n\n".join(blocks)
        out.append(
            Slide(
                index=s.index,
                title=title,
                body=body,
                # The script stays with the slide it was written for.
                notes=s.notes if k == 0 else "",
                features=_features(body),
                level=s.level if k == 0 else 2,
                layout_hint=s.layout_hint,
                class_hint=s.class_hint,
                pinned=s.pinned,
                chosen_layout=s.chosen_layout,
                lang=s.lang,
            )
        )
    return out


#: Safety factor on the floor when deciding whether a page holds its text.
PAGINATE_MARGIN = 1.1


def paginate(
    slides: list[Slide],
    catalog: list[LayoutInfo],
    *,
    min_pt: float,
    canvas: tuple[int, int] | None = None,
) -> list[Slide]:
    """Split every slide no layout can hold at *min_pt* into continuations.

    The alternative was what the assembler used to do: keep four bullets of
    ten words and drop the rest without a word. Here a slide that overruns
    even the roomiest content layout of the template becomes as many slides as
    it takes, each titled "<title> (suite)" (or "(cont.)"), split between list
    items or paragraphs. Content that cannot be split that way — a table, a
    code block, columns, an image — is kept whole and named in a warning.

    Returns
    -------
    list of Slide
        The deck, renumbered. Unchanged slides are the same objects.
    """
    content = [c for c in catalog if c.is_content_layout] or list(catalog)
    roomy = max(content, key=lambda c: pptx_fit.body_capacity(c, min_pt).chars, default=None)
    if roomy is None or not pptx_fit.body_capacity(roomy, min_pt).chars:
        return slides
    label = continuation_label(slides[0].lang if slides else "", " ".join(s.body for s in slides))
    out: list[Slide] = []

    by_name = {c.name: c for c in catalog}

    def holds(title: str, body: str, host: LayoutInfo | None = None) -> bool:
        # Measured a notch above the floor: the character model ignores
        # paragraph spacing and real glyph widths, and a split that lands
        # exactly on the estimate was observed spilling into the footer.
        report = pptx_fit.evaluate(
            pptx_fit.measure(title, body),
            host or roomy,
            min_pt=min_pt * PAGINATE_MARGIN,
            strict=True,
            canvas=canvas,
        )
        return not report.overruns

    for s in slides:
        # A slide the author pinned to a layout is measured against THAT
        # layout: the roomiest one is not where it is going.
        hinted = resolve_hint(s, catalog)
        host = by_name.get(hinted) if hinted else None
        if host is not None and not pptx_fit.body_capacity(host, min_pt).chars:
            host = None  # a title-only pinned layout: nothing to split into
        if s.title_only or holds(s.title, s.body, host):
            out.append(s)
            continue
        m = pptx_fit.measure(s.title, s.body)
        if m.table_rows or m.code_lines or m.image_count or "two-column" in s.features:
            logger.warning(
                "slide %d (%r) does not fit its layout(s) at %gpt and cannot be split "
                "automatically (table, code, image or columns): split it by hand",
                s.index,
                s.title,
                min_pt,
            )
            out.append(s)
            continue
        heading, blocks = _body_blocks(s.body)
        groups: list[list[str]] = []
        for block in blocks:
            # Greedy, in reading order: a block joins the current slide while
            # that slide still holds at the floor, else it opens the next.
            # A block that overflows on its own still gets a slide of its own.
            title = s.title if len(groups) <= 1 else f"{s.title} {label}"
            if groups and holds(title, "\n\n".join([*groups[-1], block]), host):
                groups[-1].append(block)
            else:
                groups.append([block])
        if len(groups) <= 1:
            logger.warning(
                "slide %d (%r) does not fit its layout(s) at %gpt and has a single "
                "block to show: shorten it",
                s.index,
                s.title,
                min_pt,
            )
            out.append(s)
            continue
        logger.warning(
            "slide %d (%r) does not fit its layout(s) at %gpt: split into %d slides",
            s.index,
            s.title,
            min_pt,
            len(groups),
        )
        out.extend(split_slide(s, groups, heading, label))
    for i, s in enumerate(out, start=1):
        s.index = i
    return out


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
    "Each slide states its heading level and its position in the deck: an H1 "
    "heading past the first slide opens a new part (section-divider), the "
    "first slide is the cover, the last one the closing.\n"
    "Prefer VARIETY: do not send most slides to one generic layout. Reserve "
    "cover/closing/section-divider for those roles.\n\n"
)


def resolve_hint(s: Slide, catalog: list[LayoutInfo]) -> str | None:
    """The layout an explicit hint on *s* names in this template, or ``None``.

    ``{layout="Big Number"}`` must name a layout exactly (a case-insensitive
    match is accepted, and said so); a class (:data:`CLASS_HINTS`) resolves to
    a layout of the conventional name first and to its archetype second. A
    hint the template cannot honour is reported and leaves the slide to the
    ordinary selection: a typo in a hint must not cost the slide its layout.
    """
    names = {c.name: c for c in catalog}
    folded = {c.name.casefold(): c.name for c in catalog}
    if s.layout_hint:
        if s.layout_hint in names:
            return s.layout_hint
        if s.layout_hint.casefold() in folded:
            return folded[s.layout_hint.casefold()]
        logger.warning(
            "slide %d: {layout=%r} is not a layout of this template (it has: %s)",
            s.index,
            s.layout_hint,
            ", ".join(sorted(names)),
        )
    if s.class_hint:
        archetype, wanted = CLASS_HINTS.get(s.class_hint, (None, ()))
        for name in wanted:
            if name.casefold() in folded:
                return folded[name.casefold()]
        if archetype:
            hit = next(
                (c.name for c in catalog if c.is_content_layout and c.archetype == archetype), None
            )
            if hit:
                return hit
    return None


def _catalog_block(content: list[LayoutInfo], *, min_pt: float | None = None) -> str:
    """Render the layout catalog for the prompt.

    With *min_pt* set, each line also states how much text that layout's body
    placeholders actually hold at that size. The model was previously asked to
    match content to layouts while being told nothing about either side's
    dimensions; the capacity is the half it could not guess.
    """
    lines = []
    for c in content:
        line = f"- {c.name} [{c.archetype}] {c.caption}".rstrip()
        if min_pt is not None:
            line += f" | holds {pptx_fit.capacity_for_prompt(c, min_pt=min_pt)}"
        lines.append(line)
    return "\n".join(lines)


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
    min_pt: float = pptx_fit.KAWASAKI_MIN_PT,
    strict: bool = False,
    template: Path | None = None,
    image_base_dir: Path | None = None,
) -> None:
    """Fill ``slide.chosen_layout`` for every slide via batched LLM text calls.

    Only *content* layouts are offered (brand-reference pages are dropped),
    each tagged with its archetype so the model matches by role. On any
    transport failure, slides in that batch fall back to the best
    archetype-matching content layout (never left unassigned).

    A slide with an explicit hint (:func:`resolve_hint`) is placed on that
    layout without asking anyone, and *pinned* there.

    With *strict*, a layout that cannot hold the content at *min_pt* does not
    fit at all (:func:`md2star.pptx_fit.evaluate`), so an overflowing slide
    goes to a roomier layout instead of being shrunk on a cramped one. When
    nothing holds it, the lenient ranking is kept so the slide still lands on
    the best of what there is.
    """
    content = [c for c in catalog if c.is_content_layout]
    if not content:
        return
    total = len(slides)
    for s in slides:
        hinted = resolve_hint(s, catalog)
        if hinted is not None:
            s.chosen_layout = hinted
            s.chosen_confidence = 1.0
            s.chosen_why = "explicit hint in the Markdown"
            s.pinned = True
    # First-seen wins per archetype: catalog order runs most-used layout
    # first (see extract_layouts' final sort), so this favours the
    # template's more common/representative layout for each role.
    by_archetype: dict[str, str] = {}
    for c in content:
        by_archetype.setdefault(c.archetype, c.name)
    names = {c.name for c in content}
    fallback = by_archetype.get("bulleted-content", content[0].name)
    # Layouts that carry a role are only placed by a hint or by their role
    # (first/last slide, a level-1 heading), never by the model's taste.
    reserved = {
        c.name for c in content if c.archetype in ("cover", "closing", "section-divider")
    } | {n for n in names if n.lower() in ("recap", "agenda", "closing")}
    cat_txt = _catalog_block(content, min_pt=min_pt)
    # The canvas lets the compositional checks ask where a box falls *on the
    # slide*; the image directory lets the aspect check read real dimensions.
    # Both are optional: without them those checks score 0 rather than fail.
    canvas = slide_size(template) if template is not None else None
    chat = chat or default_chat(kind="llm")

    # Batched, not one call per slide: keeps the prompt (and cost) bounded for
    # a long deck while still giving the model several slides' worth of
    # context at once to reason about variety across the batch.
    for start in range(0, len(slides), batch):
        group = slides[start : start + batch]
        # Describe each slide by how much content it holds, not only by what
        # kind. "features: table, bullets" says nothing about whether the
        # designer's three-bullet layout can carry nine long ones, and the
        # amount is exactly what decides that. See :mod:`md2star.pptx_fit`.
        listing_lines = []
        for s in group:
            # A cover or a closing is measured as what the assembler will
            # actually place: the title, alone. Measuring its markup instead
            # asks the fit model to find room for body text nobody will set.
            metrics = pptx_fit.measure(s.title, "" if s.title_only else s.body)
            if s.title_only:
                # And a slide that is a heading and nothing else *is* a big
                # statement, which is the one case the fit model already knows
                # wants the stage to itself (see pptx_fit.evaluate).
                metrics.big_statement = True
            s.metrics = metrics
            ordered = pptx_fit.rank(
                metrics,
                content,
                min_pt=min_pt,
                strict=strict,
                canvas=canvas,
                base_dir=image_base_dir,
            )
            if strict and not any(rep.fits for _, rep in ordered):
                logger.warning(
                    "slide %d (%r) overflows every layout at %gpt", s.index, s.title, min_pt
                )
                ordered = pptx_fit.rank(
                    metrics, content, min_pt=min_pt, canvas=canvas, base_dir=image_base_dir
                )
            s.fit_ranked = ordered
            if s.pinned:
                continue
            # A figure is placed by measurement, not by vote: one image and a
            # few words go wherever that image, fitted to its own aspect, comes
            # out largest. A wide figure in a half-width picture box is shrunk
            # to a third of the slide, and no caption or tie-break notices.
            # Pictures in columns first: one image beside its words, or two
            # side by side, go on the layout whose columns show them largest.
            # Scored as a lone figure, the slide won a full-width picture box
            # and its picture was laid over the other column's words.
            biggest = largest_columns_layout(
                "" if s.title_only else s.body,
                [c for c in content if c.name not in reserved],
                base_dir=image_base_dir,
                canvas=canvas,
            ) or largest_picture_layout(metrics, content, base_dir=image_base_dir)
            if biggest is not None:
                s.chosen_layout = biggest
                s.chosen_confidence = 1.0
                s.chosen_why = "the layout where the image comes out largest"
                s.pinned = True
                continue
            # Offer the geometrically plausible layouts first, by name, so the
            # model is steered by what can actually hold the content rather
            # than by which name reads well.
            plausible = [lay.name for lay, rep in ordered if rep.fits][:6]
            refused = [
                f"{lay.name} ({rep.reasons[0]})"
                for lay, rep in ordered
                if not rep.fits and rep.reasons
            ][:3]
            where = "first" if s.index == 1 else "last" if s.index == total else "middle"
            line = (
                f"[{s.index}] title: {s.title!r} | heading: "
                f"{'H' + str(s.level) if s.level else 'none'} | position: "
                f"{s.index}/{total} ({where}) | features: "
                f"{', '.join(s.features) or 'plain text'} | "
                f"content: {pptx_fit.summarise_for_prompt(metrics)}"
            )
            if plausible:
                line += f" | fits (best first): {', '.join(plausible)}"
            if refused:
                line += f" | cannot hold it: {'; '.join(refused)}"
            listing_lines.append(line)
        if not listing_lines:
            continue  # every slide of this batch was pinned by a hint
        listing = "\n".join(listing_lines)
        prompt = (
            f"{_SELECT_PROMPT_HEADER}TEMPLATE LAYOUT CATALOG (content layouts only):\n{cat_txt}\n\n"
            f"MARKDOWN SLIDES:\n{listing}\n\n"
            'Reply as JSON {"choices":[{index, layout_name, confidence, why}]} '
            "with one entry per slide. layout_name MUST be one of the catalog "
            "names; why <= 12 words."
        )
        out = chat(prompt, None, _SELECT_SCHEMA)
        # A transport failure (None) or a malformed reply both come back as
        # ``None`` here; an empty choices list means every slide in this batch
        # falls through to the archetype-fallback branch below.
        choices = (parse_json_reply(out) or {}).get("choices", [])
        by_index = {c.get("index"): c for c in choices}
        for s in group:
            if s.pinned:
                continue
            c = by_index.get(s.index) or {}
            # Reject a hallucinated layout name outright — better a sensible
            # archetype fallback than a KeyError deep in the assembler later.
            name = c.get("layout_name") if c.get("layout_name") in names else None
            why = c.get("why", "") or ""
            if name is None:
                # No usable LLM answer. Prefer the geometric ranking -- already
                # computed above -- over the categorical archetype guess: it
                # knows whether a layout can physically hold this slide, which
                # the five-rule guess cannot. This path is the common one
                # offline, so it is worth it being the better of the two.
                best = next((lay for lay, rep in s.fit_ranked if rep.fits), None)
                if best is not None:
                    name = best.name
                    why = "best geometric fit (no model)"
                else:
                    name = by_archetype.get(_archetype_fallback(s.features), fallback)
                    why = "archetype fallback"
            elif name not in {lay.name for lay, rep in s.fit_ranked if rep.fits}:
                # The model named a layout that cannot hold the content. Keep
                # its choice only if nothing fits at all; otherwise the
                # geometry wins, because it is checkable and the preference is
                # not.
                best = next((lay for lay, rep in s.fit_ranked if rep.fits), None)
                if best is not None:
                    report = next(rep for lay, rep in s.fit_ranked if lay.name == name)
                    reason = report.reasons[0] if report.reasons else "cannot hold the content"
                    osh.info(
                        "pptx: slide %d — %s cannot hold it (%s); using %s",
                        s.index,
                        name,
                        reason,
                        best.name,
                    )
                    name = best.name
                    why = f"geometry overrode the model ({reason})"
            if name in reserved:
                # A role layout (cover, divider, closing, recap, agenda) is the
                # author's to give: the model put an ordinary list on the dark
                # recap page three times in one deck, and the room reads every
                # such page as "this is what to remember".
                alt = next(
                    (lay for lay, rep in s.fit_ranked if rep.fits and lay.name not in reserved),
                    None,
                )
                if alt is not None:
                    why = f"{name} is reserved for its role; {why}"
                    name = alt.name
            s.chosen_layout = name
            s.chosen_confidence = c.get("confidence")
            s.chosen_why = why


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
    "SLIDE:\ntitle: {title!r}\nfeatures: {features}\ncontent: {content}\n\n"
    'Reply as JSON {{"best": <one of {names}>, "why": <<=12 words>}}.'
)


def _body_boxes(layout: LayoutInfo) -> int:
    return sum(1 for p in layout.placeholders if p.kind in ("body", "obj", "subTitle"))


def _alternates_for(
    s: Slide, catalog_by_name: dict[str, LayoutInfo], k: int, *, any_page: bool = False
) -> list[LayoutInfo]:
    """Pick up to *k* candidate layouts for the visual tie-break: the current
    pick plus archetype-diverse alternates (so the VLM sees a real choice, not
    near-duplicates).

    The alternates come from **this slide's own geometric ranking** when it has
    one (``fit_ranked``, computed by :func:`select_layouts` from the content's
    measured quantities against each layout's capacity). A tie-break is an
    arbitration between layouts that can actually hold the slide; offering a
    vision model whichever layouts the catalog happens to list first is how it
    ends up recommending a two-column content design for a cover. Without a
    ranking — a caller that skipped the fit stage — catalog order is the
    fallback it always was.
    """
    chosen = catalog_by_name.get(s.chosen_layout) if s.chosen_layout else None
    fitting = [lay for lay, rep in (getattr(s, "fit_ranked", None) or []) if rep.fits]
    # Only layouts with a rendered example are eligible: without one there is
    # no thumbnail to show the vision model, so it could never be picked.
    # *any_page* lifts that rule when the caller can render a layout itself
    # (:func:`default_render_layout`).
    # A slide in columns is only offered layouts with a body box per column:
    # asked to compare, a vision model moved two-column slides onto
    # one-box layouts as "primarily text-based".
    columns = getattr(getattr(s, "metrics", None), "columns", 0) or 0
    pool = [
        c
        for c in (fitting or catalog_by_name.values())
        if c.is_content_layout
        and (any_page or c.example_pages)
        and (columns < 2 or _body_boxes(c) >= columns)
    ]
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


#: A visual tie-break may not, on its own, make a deck monotonous. It is an
#: arbitration between near-equals, and a designer who shipped twenty layouts
#: did not draw them so that one could carry every slide — so once a layout
#: already carries this share of the deck, a further override onto it is
#: declined and the measured text pick (which weighed *this* slide's own
#: quantities against the layout's capacity) stands. Overrides that move a
#: slide *away* from a crowded layout are never affected.
VISUAL_VARIETY_SHARE = 0.5


#: Renders one layout of a template on its own: template path, layout name ->
#: PNG bytes, or ``None``. What the tie-break shows for a layout the template
#: never demonstrates on an example page.
RenderLayoutFn = Callable[[Path, str], "bytes | None"]


def _sample_deck(template: Path, layout_name: str, out: Path) -> bool:
    """Write a one-slide deck of *layout_name*, its placeholders labelled."""
    try:
        from pptx import Presentation  # noqa: PLC0415 — optional dependency
    except ImportError:
        return False
    prs = Presentation(str(template))
    layout = next(
        (lay for m in prs.slide_masters for lay in m.slide_layouts if lay.name == layout_name),
        None,
    )
    if layout is None:
        return False
    ids = prs.slides._sldIdLst  # noqa: SLF001 — python-pptx has no public removal API
    for sld in list(ids):
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)
    slide = prs.slides.add_slide(layout)
    for ph in slide.placeholders:
        kind = ph.placeholder_format.type
        if ph.has_text_frame:
            # The words are only there so the regions show: a vision model
            # comparing compositions needs to see where text would go.
            ph.text_frame.text = "Title" if "TITLE" in str(kind) else "Body text\nSecond point"
    prs.save(str(out))
    return True


def default_render_layout() -> RenderLayoutFn:
    """Build the real one-layout renderer (python-pptx + LibreOffice + poppler)."""
    cache: dict[tuple[str, str], bytes | None] = {}

    def _render(template: Path, layout_name: str) -> bytes | None:
        key = (osh.hashfile(str(template)), layout_name)
        if key not in cache:
            with tempfile.TemporaryDirectory() as d:
                sample = Path(d) / "layout-sample.pptx"
                pages = (
                    _render_all_pages(sample) if _sample_deck(template, layout_name, sample) else {}
                )
                cache[key] = pages.get(1)
        return cache[key]

    return _render


def _content_summary(s: Slide, limit: int = 400) -> str:
    """What the slide will actually show, in a few hundred characters."""
    if s.title_only:
        return s.subtitle[:limit] or "(none)"
    text = re.sub(r"```.*?```", "[code]", s.body, flags=re.DOTALL)
    text = _SLIDE_HEADING_RE.sub("", text)
    text = " / ".join(line.strip() for line in text.splitlines() if line.strip())
    measured = pptx_fit.summarise_for_prompt(s.metrics) if s.metrics is not None else ""
    out = f"{text[:limit]}{'…' if len(text) > limit else ''}"
    return f"{out} ({measured})" if measured else out


def visual_confirm(
    slides: list[Slide],
    catalog: list[LayoutInfo],
    *,
    chat: ChatFn | None = None,
    render: RenderFn | None = None,
    render_layout: RenderLayoutFn | None = None,
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

    See Also
    --------
    VISUAL_VARIETY_SHARE : why some overrides are declined. Observed on a real
        template: asked slide by slide, a vision model answered with the same
        layout six times out of six, and a deck of six identical compositions
        is not what any of those slides' content asked for.
    """
    if template is None:
        return
    render = render or default_render()
    render_layout = render_layout or default_render_layout()
    chat = chat or default_chat(kind="vlm")
    catalog_by_name = {c.name: c for c in catalog}

    for s in slides:
        if s.pinned:
            continue  # the author named this layout; no model second-guesses it
        if only_low_confidence:
            conf = s.chosen_confidence
            # A missing confidence (transport failure -> archetype fallback)
            # is treated as "worth checking", not skipped — it's exactly the
            # case where the text stage had the least signal to go on.
            if conf is not None and conf >= confidence_threshold:
                continue
        candidates = _alternates_for(s, catalog_by_name, k, any_page=True)
        if len(candidates) < 2:
            continue  # nothing to tie-break against
        images: list[bytes] = []
        usable: list[LayoutInfo] = []
        for c in candidates:
            # The designer's own page when there is one; otherwise the layout
            # rendered on its own. Skipping a page-less candidate used to
            # drop the CURRENT pick from the comparison, so the tie-break
            # could only ever override it.
            page = c.rep_page
            png = render(template, page) if page is not None else render_layout(template, c.name)
            if png is None:
                continue
            # images/usable stay index-aligned: the prompt's "in this order"
            # listing must match exactly what the model is shown.
            images.append(png)
            usable.append(c)
        if len(usable) < 2:
            continue  # a render/no-example gap left too few options to compare
        if s.chosen_layout and s.chosen_layout not in {c.name for c in usable}:
            continue  # the current pick could not be shown: no fair comparison
        names = [c.name for c in usable]
        prompt = _VISUAL_PROMPT.format(
            names=", ".join(names),
            title=s.title,
            # What the assembler will place, not what the markup happens to
            # contain: told "features: plain text" for a cover, a vision model
            # reasonably picks a layout with room for supporting text, and
            # there will be none.
            features=(
                "none — this is a cover/closing slide: the heading alone, no body text"
                if s.title_only
                else ", ".join(s.features) or "plain text"
            ),
            content=_content_summary(s),
        )
        out = chat(prompt, images, _VISUAL_SCHEMA)
        data = parse_json_reply(out)
        if not data:
            continue
        best = data.get("best")
        if best in names and best != s.chosen_layout:
            crowd = sum(1 for o in slides if o is not s and o.chosen_layout == best)
            if crowd >= max(2, int(len(slides) * VISUAL_VARIETY_SHARE)):
                logger.info(
                    "visual tie-break declined for slide %d: %s already carries %d of %d slides",
                    s.index,
                    best,
                    crowd,
                    len(slides),
                )
                continue
            logger.info(
                "visual tie-break overrides slide %d: %s -> %s (%s)",
                s.index,
                s.chosen_layout,
                best,
                data.get("why", ""),
            )
            s.chosen_layout = best
            s.chosen_why = str(data.get("why", "")) or s.chosen_why


def largest_picture_layout(metrics, content, *, base_dir: Path | None = None) -> str | None:
    """Name of the layout whose picture box shows a lone image largest, or ``None``.

    Applies only to a slide that is one image and few words, with a readable
    image file. Each candidate's first picture region is scored by the area
    the image takes once fitted to its own aspect inside that box; the largest
    wins. ``None`` (no image, too much text, unreadable file, no picture box)
    leaves the slide to the ordinary ranking.
    """
    if metrics.image_count != 1 or not metrics.is_sparse or not metrics.image_paths:
        return None
    resolved = pptx_fit._resolve(metrics.image_paths[0], base_dir)
    aspect = pptx_fit._image_aspect(resolved) if resolved else None
    if not aspect:
        return None
    best: tuple[float, str] | None = None
    for lay in content:
        for ph in getattr(lay, "placeholders", None) or []:
            if (getattr(ph, "kind", "") or "") not in pptx_fit._PIC_KINDS or not getattr(
                ph, "emu", None
            ):
                continue
            _, _, bw, bh = ph.emu
            if bw <= 0 or bh <= 0:
                continue
            w = min(bw, bh * aspect)
            area = w * (w / aspect)
            if best is None or area > best[0]:
                best = (area, lay.name)
            break
    return best[1] if best else None


def split_columns(body: str) -> list[str]:
    """The bodies of a slide's ``::: {.column}`` divs, in order (``[]`` if none)."""
    columns: list[list[str]] = []
    stack: list[bool] = []  # True for a column div
    for line in body.splitlines():
        s = line.strip()
        if re.match(r"^:{3,}[ \t]*$", s) and stack:
            stack.pop()
            continue
        if re.match(r"^:{3,}[ \t]*\S", s):
            is_col = bool(
                re.match(r"^:{3,}[ \t]*(?:\{[^}]*\.column\b(?!s)[^}]*\}|column\b(?!s))", s)
            )
            stack.append(is_col)
            if is_col:
                columns.append([])
            continue
        if any(stack) and columns:
            columns[-1].append(line)
    return ["\n".join(c) for c in columns] if len(columns) >= 2 else []


#: Space left between the title's bottom edge and a stage drawn under it, and
#: the share of the canvas kept free at its foot when nothing else bounds it.
_STAGE_GAP = 0.02
_STAGE_FOOT = 0.92


def column_regions(
    info: LayoutInfo | None, n: int, canvas: tuple[int, int] | None = None
) -> list[tuple[int, int, int, int]] | None:
    """Where *n* side-by-side columns go on *info*, in EMU, left to right.

    The layout's own body boxes when it has *n* of them (the *n* largest, so a
    "Comparison" layout's small header boxes lose to the content boxes under
    them). Otherwise the stage under a full-width title, cut in *n* equal
    parts: that is how a "Title Only" layout holds two pictures. ``None`` when
    the layout has neither (its title sits beside the content, as on "Picture
    with Caption"), which is the layout's way of saying it cannot hold columns.

    The assembler places columns with this same geometry, so the layout chosen
    for a column slide is chosen for the boxes its columns will really get.
    """
    if info is None or n < 2:
        return None
    phs = [p for p in info.placeholders if p.emu is not None and p.kind not in _LATENT_KINDS]
    bodies = [p.emu for p in phs if p.kind in ("body", "obj")]
    if len(bodies) >= n:
        biggest = sorted(bodies, key=lambda b: -b[2] * b[3])[:n]
        return sorted(biggest, key=lambda b: b[0])  # type: ignore[return-value]
    stage = stage_region(info, canvas)
    if stage is None:
        return None
    left, top, span, height = stage
    sep = int(span * 0.025)
    each = (span - sep * (n - 1)) // n
    return [(left + k * (each + sep), top, each, height) for k in range(n)]


def stage_region(
    info: LayoutInfo | None, canvas: tuple[int, int] | None = None
) -> tuple[int, int, int, int] | None:
    """The area under a full-width title, down to the lowest content box, in EMU.

    ``None`` when the layout has no title, a title beside the content rather
    than over it, or a title that fills the page and leaves no stage.
    """
    if info is None:
        return None
    phs = [p for p in info.placeholders if p.emu is not None and p.kind not in _LATENT_KINDS]
    title = next((p.emu for p in phs if p.kind in ("title", "ctrTitle")), None)
    if title is None:
        return None
    others = [p.emu for p in phs if p.kind not in ("title", "ctrTitle")]
    width = canvas[0] if canvas else max([title[0] + title[2], *(b[0] + b[2] for b in others)])
    height = canvas[1] if canvas else width * 9 // 16
    if title[2] < 0.5 * width:
        return None  # a side title: the area under it is a margin, not a stage
    top = title[1] + title[3] + int(height * _STAGE_GAP)
    below = [b[1] + b[3] for b in others if b[1] + b[3] > top]
    bottom = max(below) if below else int(height * _STAGE_FOOT)
    if bottom - top < 0.4 * height:
        return None  # a title that fills the page leaves no stage under it
    return (title[0], top, title[2], bottom - top)


_COLUMN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*<?([^)\s>]+)")


def largest_columns_layout(
    body: str,
    content,
    *,
    base_dir: Path | None = None,
    canvas: tuple[int, int] | None = None,
) -> str | None:
    """Name of the layout whose columns show this slide's pictures largest, or ``None``.

    Applies only to a slide in columns where at least one column carries an
    image (two pictures side by side, or a picture beside its words). Each
    candidate's columns (:func:`column_regions`) are scored by the area the
    *smallest* of the pictures takes once fitted to its own aspect inside its
    column, so neither of two pictures is sacrificed to the other. ``None``
    leaves the slide to the ordinary ranking: no image in a column, an
    unreadable file, no layout able to hold the columns.
    """
    cols = split_columns(body)
    if not cols:
        return None
    aspects: list[float | None] = []
    for col in cols:
        m = _COLUMN_IMAGE_RE.search(col)
        if m is None:
            aspects.append(None)
            continue
        resolved = pptx_fit._resolve(m.group(1), base_dir)
        aspect = pptx_fit._image_aspect(resolved) if resolved else None
        if not aspect:
            return None
        aspects.append(aspect)
    if not any(aspects):
        return None
    best: tuple[float, str] | None = None
    for lay in content:
        regions = column_regions(lay, len(cols), canvas)
        if not regions:
            continue
        smallest = min(
            min(bw, bh * a) ** 2 / a
            for (_, _, bw, bh), a in zip(regions, aspects, strict=False)
            if a
        )
        if best is None or smallest > best[0]:
            best = (smallest, lay.name)
    return best[1] if best else None
