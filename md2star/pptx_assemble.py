"""Seam-D PPTX assembler: build a deck directly on the AI-selected layouts.

:mod:`md2star.pptx_layout` decides, per slide, which of a designer template's
named layouts best carries that slide's content. This module is what actually
**uses** that decision: for every slide it instantiates the *chosen* layout
(not a fixed handful of curated backgrounds) from the real template and
overlays guaranteed-legible content, so the deck's visual variety follows the
AI's per-slide reasoning instead of a hand-picked round-robin.

Design choice, carried over from the PoC that proved it out: fighting a
designer layout's own placeholders is fragile (their colours and geometry vary
wildly, some are dark-on-dark, some clutter a small box next to a big void).
Instead each slide keeps the chosen layout's **background** (its true
branding) and places **our own guaranteed-safe text/image boxes** in it, sized
from the layout's actual placeholder geometry when the catalog recorded one
(title / body / picture), and a sensible fractional default otherwise — so it
degrades gracefully for template layouts the catalog under-described.

With one exception, reconciled rather than overlaid: **the title goes into the
layout's own title placeholder** when it has one. A slide's outline entry and
its screen-reader reading order come from placeholders, not from loose text
boxes, so a deck built purely of overlays had no titles at all where it counts
— and the empty placeholder left underneath each overlay was a "Click to add
title" ghost and a guaranteed overlap. Body text keeps its overlay (a designer
body placeholder brings its master's own bullet glyphs, which would double up
with the assembler's), and every placeholder still empty once a slide is
finished is removed. See the "placeholder / overlay reconciliation" section.

Text colour is not hard-coded white: with an arbitrary designer layout now in
play (not just a curated dark subset), a slide's background can be light, so
the assembler reads the layout's own background colour and switches to a dark
foreground when needed. This is the correctness gap the curated-background PoC
never had to close.

A layout is not the whole template, though, and ``reference_slides=True`` opts
each slide into **Seam E** (:mod:`md2star.pptx_clone`) first: where the chosen
layout has an example page in the template that can carry this slide's content,
that *page* is cloned and its text replaced, so the slide inherits the
designer's decorative shapes and typography and not just their background. It
is strictly an addition — every refusal falls through to the Seam-D path above,
which can place anything.

The **target-matching Ralph Eyeball Loop** (:func:`eyeball_slides`) closes the
verification gap the same way :mod:`md2star.reverse_diagrams` does for
diagrams: render the assembled slide, show it *and* the chosen layout's own
catalog thumbnail to a vision model, and apply bounded, spec-level fixes
(shrink text, trim bullets, grow an undersized image) rather than ever hand-
editing the picture. Its model-free counterpart is :mod:`md2star.pptx_audit`,
which measures the saved deck for the defects arithmetic can settle on its own.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import re
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_FILL
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

from .logging import get_logger
from .pptx_layout import (
    ChatFn,
    LayoutInfo,
    RenderFn,
    Slide,
    default_chat,
    default_render,
    parse_json_reply,
    render_deck_pages,
)

logger = get_logger(__name__)

_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
_NEAR_BLACK = RGBColor(0x14, 0x14, 0x16)
_CODE_BG = RGBColor(0x14, 0x14, 0x16)
_CODE_FG = RGBColor(0xEA, 0xEA, 0xEA)

_EMOJI = re.compile("[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f1e6-\U0001f1ff️]")

# Families that ship with the OS — never treated as "the template's design
# font" when picking the most common typeface (see :func:`template_fonts`).
_SYSTEM_FONTS = {
    "arial",
    "calibri",
    "helvetica",
    "helvetica neue",
    "times",
    "times new roman",
    "cambria",
    "verdana",
    "tahoma",
    "georgia",
    "courier",
    "courier new",
    "segoe ui",
}
_WEIGHTS = (
    "black",
    "extrablack",
    "extrabold",
    "extra bold",
    "heavy",
    "bold",
    "semibold",
    "semi bold",
    "demibold",
    "medium",
)

EMU_PER_INCH = 914400

#: A Markdown image, with its alt text captured separately from its path:
#: the path is what gets placed, the alt text is what a screen reader reads.
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

#: Text this short, with no real word in it, is *ornament*: the "01" / "02" of
#: a numbered-step design, an arrow, a single letter. Part of the shared shape
#: vocabulary this module owns, because two very different readers need the
#: same answer — :mod:`md2star.pptx_clone` keeps ornament on a cloned page
#: rather than retiring it, and :mod:`md2star.pptx_audit` does not count it as
#: one of the two text blocks in an overlap.
_ORNAMENT = re.compile(r"\A(?=.{1,3}\Z)(?!.*[A-Za-z]{2}).*\Z", re.DOTALL)


def is_ornament(text: str) -> bool:
    """Whether *text* is ornament (or nothing) rather than someone's words."""
    return not text or _ORNAMENT.match(text) is not None


def _clean(text: str) -> str:
    return _EMOJI.sub("", text).replace("  ", " ").strip()


# ── template introspection ───────────────────────────────────────────────────
def layout_index(prs: Presentation) -> dict[str, object]:
    """Map every distinct layout name to its ``SlideLayout`` object."""
    idx: dict[str, object] = {}
    for master in prs.slide_masters:
        for layout in master.slide_layouts:
            idx.setdefault(layout.name, layout)
    return idx


def clear_slides(prs: Presentation) -> None:
    """Drop every slide the template ships with, keeping layouts/masters."""
    # python-pptx has no public "remove slide" API; drop_rel + list removal is
    # the documented workaround (also used by md2star.postprocess elsewhere).
    lst = prs.slides._sldIdLst  # noqa: SLF001 — python-pptx exposes no public API for this
    for sld in list(lst):
        prs.part.drop_rel(sld.rId)
        lst.remove(sld)


def _bg_hex(layout) -> str | None:
    """Solid background colour as ``#RRGGBB``, or ``None`` if not resolvable."""
    try:
        fill = layout.background.fill
        if fill.type == MSO_FILL.SOLID:
            return f"#{fill.fore_color.rgb}"
    except Exception:  # noqa: BLE001 — gradient / theme-ref / no explicit bg
        return None
    return None


def is_dark_layout(layout) -> bool | None:
    """``True``/``False`` for a resolvable one-colour background, else ``None``.

    Resolved through :func:`background_rgb`, so a dark background declared on
    the master (and only inherited by the layout) counts.
    """
    rgb = background_rgb(layout)
    if rgb is None:
        return None
    # Standard perceptual luma weights (ITU-R BT.601); 110/255 is a slightly
    # conservative midpoint (below the textbook 128) so a mid-tone background
    # still gets white text, which stays legible more often than the reverse.
    return _luma(rgb) < 110


# ── template typography and colour, read the way a renderer reads them ──────
# A placeholder's look is inherited: its own <a:lstStyle>, then the layout
# placeholder it was cloned from, then the master's, then the master's
# <p:txStyles> (titleStyle for titles, bodyStyle for body text). A designer
# who built the template for 30 pt type wrote that 30 somewhere on this chain,
# and the assembler's job under --min-pt is to *find* it and leave it alone
# rather than stamp 16 pt over it.
_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_TITLE_STYLE_KINDS = {"title", "ctrTitle"}


def _qa(tag: str) -> str:
    return f"{{{_A_NS}}}{tag}"


def _qp(tag: str) -> str:
    return f"{{{_P_NS}}}{tag}"


def _master_of(shape):
    """The slide master a slide / layout / master shape ultimately inherits from."""
    part = shape.part
    try:
        if hasattr(part, "slide_layout"):
            return part.slide_layout.slide_master  # a slide's (or layout's) shape
        return getattr(part, "slide_master", None)  # a master's own shape
    except Exception:  # noqa: BLE001 — a detached shape: no inheritance to read
        return None


def _theme_colours(master) -> dict[str, RGBColor]:
    """The theme's colour scheme, by slot name (``dk1``, ``lt1``, ``accent1``...)."""
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT  # noqa: PLC0415
    from pptx.oxml import parse_xml  # noqa: PLC0415

    try:
        theme = parse_xml(master.part.part_related_by(RT.THEME).blob)
    except Exception:  # noqa: BLE001 — no theme part: nothing to resolve against
        return {}
    out: dict[str, RGBColor] = {}
    scheme = theme.find(f".//{_qa('clrScheme')}")
    if scheme is None:
        return out
    for slot in scheme:
        name = slot.tag.split("}")[-1]
        srgb = slot.find(_qa("srgbClr"))
        sys_clr = slot.find(_qa("sysClr"))
        if srgb is not None and srgb.get("val"):
            out[name] = RGBColor.from_string(srgb.get("val"))
        elif sys_clr is not None and sys_clr.get("lastClr"):
            out[name] = RGBColor.from_string(sys_clr.get("lastClr"))
    return out


def _resolve_colour(fill_parent, master) -> RGBColor | None:
    """The RGB of a ``solidFill`` / ``bgRef`` / gradient's first stop, if knowable.

    A ``schemeClr`` goes through the master's ``clrMap`` (``tx1`` -> ``dk1``)
    to the theme. Luminance modifiers (``lumMod``...) are ignored: close
    enough to say "dark or light", which is all the callers ask.
    """
    if fill_parent is None:
        return None
    srgb = fill_parent.find(f".//{_qa('srgbClr')}")
    if srgb is not None and srgb.get("val"):
        return RGBColor.from_string(srgb.get("val"))
    scheme = fill_parent.find(f".//{_qa('schemeClr')}")
    if scheme is None or master is None:
        return None
    slot = scheme.get("val", "")
    clr_map = master._element.find(_qp("clrMap"))  # noqa: SLF001
    if clr_map is not None and clr_map.get(slot):
        slot = clr_map.get(slot)
    return _theme_colours(master).get(slot)


def _bg_element(part_obj):
    try:
        return part_obj._element.cSld.bg  # noqa: SLF001 — python-pptx has no reader for bgRef
    except Exception:  # noqa: BLE001
        return None


def background_rgb(layout) -> RGBColor | None:
    """The background a slide on *layout* shows, when it is one colour.

    The layout's own ``<p:bg>`` first, then its master's — the step that was
    missing: a template whose dark background is declared once on the master
    (the common case) used to read as "unresolvable", hence light, hence
    near-black text on a dark slide. A picture background is unknowable and
    returns ``None``; a gradient is judged by its first stop.
    """
    master = getattr(layout, "slide_master", None)
    for part_obj in (layout, master):
        if part_obj is None:
            continue
        bg = _bg_element(part_obj)
        if bg is None:
            continue
        if bg.find(f".//{_qa('blipFill')}") is not None:
            return None
        return _resolve_colour(bg, master)
    return None


def _luma(rgb: RGBColor) -> float:
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _style_levels(shape, level: int) -> list:
    """Every ``lvlNpPr`` that styles *shape*'s paragraphs at *level*, nearest first."""
    tag = _qa(f"lvl{min(level, 8) + 1}pPr")
    found = []
    node = shape
    seen = 0
    while node is not None and seen < 4:
        seen += 1
        el = node._element  # noqa: SLF001
        lst = el.find(f".//{_qa('lstStyle')}")
        if lst is not None and lst.find(tag) is not None:
            found.append(lst.find(tag))
        try:
            node = node._base_placeholder  # noqa: SLF001 — slide -> layout -> master
        except Exception:  # noqa: BLE001 — a master placeholder has no base
            node = None
    master = _master_of(shape)
    if master is not None:
        styles = master._element.find(_qp("txStyles"))  # noqa: SLF001
        if styles is not None:
            kind = placeholder_kind(shape)
            which = (
                "titleStyle"
                if kind in _TITLE_STYLE_KINDS
                else "bodyStyle"
                if shape.is_placeholder
                else "otherStyle"
            )
            sheet = styles.find(_qp(which))
            if sheet is not None and sheet.find(tag) is not None:
                found.append(sheet.find(tag))
    return found


def declared_style(shape, level: int = 0) -> tuple[float | None, RGBColor | None, bool]:
    """The point size and colour *shape* inherits at *level*, from the template.

    Returns
    -------
    tuple of (float or None, RGBColor or None, bool)
        The inherited size (``None`` when nothing on the chain declares one),
        its colour when resolvable to RGB, and whether a colour is declared at
        all (a theme colour the reader cannot resolve still counts: the
        designer chose it, so the assembler should not paint over it).
    """
    size: float | None = None
    colour: RGBColor | None = None
    declared = False
    master = None
    for lvl in _style_levels(shape, level):
        rpr = lvl.find(_qa("defRPr"))
        if rpr is None:
            continue
        if size is None and rpr.get("sz"):
            size = int(rpr.get("sz")) / 100.0
        fill = rpr.find(_qa("solidFill"))
        if not declared and fill is not None:
            declared = True
            master = master or _master_of(shape)
            colour = _resolve_colour(fill, master)
    return size, colour, declared


def _weight_rank(name: str) -> int:
    low = name.lower()
    for i, w in enumerate(_WEIGHTS):
        if w in low:
            return i
    return len(_WEIGHTS)


def template_fonts(template: Path) -> dict[str, str]:
    """Derive the template's own DESIGN fonts: ``{family, display, body}``.

    Reads every explicit ``typeface="..."`` on slide/layout shapes (not the
    theme, which carries Office's long CJK fallback list) and picks the most-
    common non-system face as *body*, its heaviest same-family weight as
    *display* (titles). Falls back to Arial when the template declares no
    explicit design font. Read-only: unlike the PoC this is derived from, this
    never downloads or installs fonts — a missing font degrades to whatever
    substitute PowerPoint/LibreOffice picks, exactly like every other
    best-effort AI/rendering feature in this package.
    """
    counts: Counter = Counter()
    with zipfile.ZipFile(template) as z:
        for name in z.namelist():
            if re.search(r"ppt/(slides|slideLayouts)/.*\.xml$", name):
                xml = z.read(name).decode("utf-8", "replace")
                for f in re.findall(r'typeface="([^"]+)"', xml):
                    # "+mn-lt"/"+mj-lt" are theme placeholders, not real
                    # typeface names — an explicit face always wins over them.
                    if f and not f.startswith("+"):
                        counts[f] += 1
    design = [(f, k) for f, k in counts.items() if f.lower() not in _SYSTEM_FONTS]
    if not design:
        face = counts.most_common(1)[0][0] if counts else "Arial"
        return {"family": face.split(" ")[0], "display": face, "body": face}
    # The most-frequent non-system face is almost always body text (there's
    # far more prose than titles in a real deck) — a cheap, reliable proxy
    # for "the template's body font" without parsing which shape is which.
    body_face = max(design, key=lambda x: x[1])[0]
    family = body_face.split(" ")[0]
    variants = [f for f, _ in design if f.split(" ")[0] == family]
    # The heaviest same-family variant in actual use is the designer's own
    # title weight (e.g. "Montserrat ExtraBold" next to plain "Montserrat").
    display = min(variants, key=_weight_rank)
    plain = [v for v in variants if v.lower() == family.lower()]
    return {"family": family, "display": display, "body": plain[0] if plain else body_face}


# ── content parsing ──────────────────────────────────────────────────────────
def is_content(features: list[str]) -> bool:
    return (
        bool({"bullets", "ordered-list", "table"} & set(features))
        and "big-statement" not in features
    )


def parse_image(body: str, base_dir: Path | None) -> Path | None:
    m = _IMAGE_RE.search(body)
    if not m or base_dir is None:
        return None
    # split()[0] drops a Markdown title suffix (`"foo.png "optional title""`);
    # a non-existent resolved path returns None rather than a dangling Path,
    # so the caller's `if img:` branch check works without a stat() of its own.
    cand = (base_dir / m.group(2).split()[0]).resolve()
    return cand if cand.exists() else None


def parse_alt_text(body: str) -> str:
    """The first image's Markdown alt text (``""`` when it has none).

    Authored alt text is the accessible description of the picture, and
    dropping it makes the deck unreadable to a screen reader. Pandoc's own
    PPTX writer carries it into the shape's ``descr`` attribute; this is how
    the assembler keeps parity with the path it bypasses. md2star can even
    *write* this text for you — see :mod:`md2star.preprocessing.alt_text`.
    """
    m = _IMAGE_RE.search(body)
    return m.group(1).strip() if m else ""


def parse_mermaid(body: str) -> str | None:
    m = re.search(r"```mermaid\s*\n(.*?)```", body, re.DOTALL)
    return m.group(1).strip() if m else None


def parse_code(body: str) -> str | None:
    """First non-Mermaid fenced block (the slide's primary code sample, if any)."""
    for m in re.finditer(r"```(\w*)\s*\n(.*?)```", body, re.DOTALL):
        if m.group(1).lower() != "mermaid":
            return m.group(2).strip()
    return None


@dataclass
class Item:
    """One paragraph of slide text: its words, list depth, and whether it is a bullet."""

    text: str
    level: int = 0
    bullet: bool = True


_LIST_ITEM_RE = re.compile(r"^([ \t]*)([-*+]|\d+[.)])[ \t]+(.*)$")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_SPAN_ATTR_RE = re.compile(r"\[([^\]]*)\]\{[^}]*\}")


def _inline(text: str) -> str:
    """Markdown inline markup -> the words a reader sees."""
    text = _SPAN_ATTR_RE.sub(r"\1", text)
    text = _LINK_RE.sub(r"\1", text)
    text = re.sub(r"\s*\{[^{}]*\}\s*$", "", text)
    text = re.sub(r"\*\*|__|`", "", text)
    # Single-character emphasis only where it wraps words, so snake_case and
    # 2*3 survive.
    text = re.sub(r"(?<![\w*])[*_](\S(?:[^*_]*\S)?)[*_](?![\w*])", r"\1", text)
    return _clean(text)


def body_items(body: str) -> list[Item]:
    """Every paragraph of visible text on a slide, in order, nothing capped.

    Headings, tables, fences, images and div markers are not text paragraphs
    (each has its own branch in :func:`assemble`). List items keep their depth
    (two spaces or a tab per level); a numbered item keeps its number and gets
    no bullet glyph; wrapped lines join the paragraph they continue.
    """
    body = re.sub(r"(?ms)^[ \t]*(```+|~~~+).*?^[ \t]*\1[ \t]*$", "", body)
    items: list[Item] = []
    para: list[str] = []
    in_list = False

    def flush() -> None:
        if para:
            text = _inline(" ".join(para))
            if text:
                items.append(Item(text, 0, False))
            para.clear()

    for raw in body.splitlines():
        s = raw.strip()
        if not s:
            flush()
            in_list = False
            continue
        if s.startswith(("#", "|", ":::")) or _IMAGE_RE.fullmatch(s) or set(s) <= {"*", "-", " "}:
            flush()
            in_list = False
            continue
        m = _LIST_ITEM_RE.match(raw)
        if m:
            flush()
            indent = len(m.group(1).replace("\t", "  "))
            marker = m.group(2)
            text = _inline(m.group(3))
            if marker[0].isdigit():
                items.append(Item(f"{marker.rstrip(')').rstrip('.')}. {text}", indent // 2, False))
            elif text:
                items.append(Item(text, min(indent // 2, 4), True))
            in_list = True
            continue
        if in_list and items and raw[:1] in (" ", "\t"):
            items[-1].text = f"{items[-1].text} {_inline(s)}".strip()
            continue
        para.append(s[1:].strip() if s.startswith(">") else s)
    flush()
    return items


def fallback_bullets(body: str, cap: int | None = None) -> list[str]:
    """The slide's text paragraphs, markup stripped — all of them unless *cap*.

    There used to be a default cap of four bullets of ten words each, applied
    silently. That was content loss presented as layout; the full text now
    goes on the slide, and a slide too long for any layout is split into
    continuation slides upstream (:func:`md2star.pptx_layout.paginate`).
    """
    texts = [it.text for it in body_items(body)]
    return texts if cap is None else texts[:cap]


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


def parse_table(body: str) -> list[list[str]]:
    """The first Markdown pipe table on the slide, as rows of cell text."""
    rows: list[list[str]] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("|") and s.endswith("|"):
            if re.fullmatch(r"[\s|:-]+", s):
                continue  # the |---|---| separator row is structure, not content
            rows.append([_inline(c.strip()) for c in s.strip("|").split("|")])
        elif rows:
            break
    return rows


def notes_paragraphs(notes: str) -> list[tuple[str, int]]:
    """Speaker notes as ``(text, level)`` paragraphs, list structure kept.

    The notes pane is read mid-talk, at a glance: one paragraph per bullet,
    with the bullet drawn as "•" and nested items indented, reads the way the
    author wrote it — a single blob, or raw "- " markup, does not.
    """
    out: list[tuple[str, int]] = []
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append((_inline(" ".join(para)), 0))
            para.clear()

    for raw in notes.splitlines():
        s = raw.strip()
        if not s:
            flush()
            continue
        m = _LIST_ITEM_RE.match(raw)
        if m:
            flush()
            level = len(m.group(1).replace("\t", "  ")) // 2
            marker = m.group(2)
            glyph = "•" if not marker[0].isdigit() else marker
            out.append((f"{glyph} {_inline(m.group(3))}", min(level, 4)))
            continue
        if out and not para and raw[:1] in (" ", "\t"):
            text, level = out[-1]
            out[-1] = (f"{text} {_inline(s)}", level)
            continue
        para.append(s)
    flush()
    return [(t, lvl) for t, lvl in out if t]


# ── placeholder-aware boxing ──────────────────────────────────────────────────
# Fractional (left, top, width, height) defaults over the ACTUAL slide size —
# used only when the chosen layout's catalog entry recorded no matching
# placeholder geometry, so this degrades safely for any aspect ratio.
_DEFAULT_TITLE_BOX = (0.06, 0.06, 0.88, 0.22)
_DEFAULT_DIVIDER_BOX = (0.08, 0.28, 0.84, 0.44)
_DEFAULT_BODY_BOX = (0.06, 0.30, 0.88, 0.62)
_DEFAULT_IMAGE_BOX = (0.05, 0.20, 0.90, 0.75)

#: Placeholder kinds that are a slide heading. Public because Seam E
#: (:mod:`md2star.pptx_clone`) classifies a designer page with the same
#: vocabulary the assembler writes with.
TITLE_KINDS = {"title", "ctrTitle"}
_BODY_KINDS = {"body", "subTitle"}
_IMAGE_KINDS = {"pic"}


def _placeholder_box_in(
    info: LayoutInfo | None, kinds: set[str]
) -> tuple[float, float, float, float] | None:
    """The first matching placeholder's box, in inches, or ``None``."""
    if info is None:
        return None
    for ph in info.placeholders:
        if ph.kind in kinds and ph.emu is not None:
            left, top, width, height = ph.emu
            return (
                left / EMU_PER_INCH,
                top / EMU_PER_INCH,
                width / EMU_PER_INCH,
                height / EMU_PER_INCH,
            )
    return None


def _fractional_box(
    prs: Presentation, frac: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    slide_w = prs.slide_width / EMU_PER_INCH
    slide_h = prs.slide_height / EMU_PER_INCH
    left, top, width, height = frac
    return (left * slide_w, top * slide_h, width * slide_w, height * slide_h)


def content_box(prs: Presentation, info: LayoutInfo | None) -> tuple[float, float, float, float]:
    # Placeholder geometry always wins when the catalog recorded one — it's
    # the designer's own intended zone, more faithful than any guessed default.
    return _placeholder_box_in(info, _BODY_KINDS) or _fractional_box(prs, _DEFAULT_BODY_BOX)


def image_box(prs: Presentation, info: LayoutInfo | None) -> tuple[float, float, float, float]:
    return _placeholder_box_in(info, _IMAGE_KINDS) or _fractional_box(prs, _DEFAULT_IMAGE_BOX)


def title_box(
    prs: Presentation, info: LayoutInfo | None, *, divider: bool = False
) -> tuple[float, float, float, float]:
    ph = _placeholder_box_in(info, TITLE_KINDS)
    if ph is not None:
        return ph
    # No title placeholder recorded (common — Jellysmack's own layouts use
    # generic "body" placeholders even for titles): a section-divider slide
    # gets the roomier, vertically-centred default box, a normal slide the
    # slim top-strip one.
    return _fractional_box(prs, _DEFAULT_DIVIDER_BOX if divider else _DEFAULT_TITLE_BOX)


# ── placeholder / overlay reconciliation ─────────────────────────────────────
# ``prs.slides.add_slide(layout)`` *clones* the layout's placeholders onto the
# new slide. The overlay strategy above then draws its own boxes in the very
# same geometry, so without this section every assembled slide shipped a pair
# of shapes per region: our text, plus an empty placeholder under it. That is
# not cosmetic. An empty placeholder shows PowerPoint's "Click to add title"
# prompt in edit view, is what a click selects instead of the real text, and
# an unfilled picture placeholder draws its own icon frame. Worse, the slide's
# *outline* and its screen-reader reading order come from placeholders — so a
# deck whose titles are plain text boxes has no titles at all in the outline
# pane. (Doubled, exactly-coincident shapes also fail the "no overlapping
# elements" half of PPTEval's Design dimension, arXiv 2501.03936.)
#
# Reconciliation, deliberately asymmetric:
#   * the TITLE goes *into* the layout's title placeholder when it has one —
#     titles carry no bullet glyphs, so inheriting the designer's own shape is
#     safe, and it is what restores the outline and the reading order;
#   * body/picture content keeps its own guaranteed-legible overlay, because a
#     designer body placeholder brings its master's bullet characters and
#     indents, which would double up with ours;
#   * any placeholder still empty when the slide is finished is removed.
_PH_EL = "{http://schemas.openxmlformats.org/presentationml/2006/main}ph"

#: Placeholders whose emptiness is correct: PowerPoint fills the date, the
#: footer and the slide number itself, from field codes, at display time.
#: python-pptx already declines to clone these ("latent" placeholders), so in
#: practice they never reach a slide this module built — the guard is here so
#: that deleting "every empty placeholder" can never mean deleting a deck's
#: page numbers, whatever path the presentation arrived by.
LATENT_KINDS = frozenset({"dt", "ftr", "sldNum"})


def placeholder_kind(shape) -> str:
    """OOXML placeholder type of *shape* (``""`` when it is not one).

    Read off the XML rather than python-pptx's ``PP_PLACEHOLDER`` enum so the
    vocabulary is identical to the catalog extractor's
    (:func:`md2star.pptx_layout._placeholder_kind`) with no enum-name mapping
    table to keep in sync. A ``<p:ph>`` with no ``type`` is OOXML's generic
    content placeholder, which pandoc and PowerPoint both call ``obj``.
    """
    # `.//` rather than the exact nvSpPr/nvPr path: a placeholder that has been
    # filled with a picture is a <p:pic>, not a <p:sp>, and nests its <p:ph>
    # one level deeper under a different parent.
    ph = shape.element.find(f".//{_PH_EL}")
    return "" if ph is None else (ph.get("type") or "obj")


def slide_placeholder(slide, kinds: set[str]):
    """The slide's own cloned placeholder of one of *kinds*, or ``None``."""
    for shape in slide.placeholders:
        if placeholder_kind(shape) in kinds:
            return shape
    return None


def drop_empty_placeholders(slide) -> int:
    """Delete every placeholder this slide inherited but never filled.

    Returns
    -------
    int
        How many were removed — reported by the caller's debug log, and the
        invariant :func:`md2star.pptx_audit.audit` re-checks on the saved deck.
    """
    removed = 0
    for shape in list(slide.placeholders):
        if placeholder_kind(shape) in LATENT_KINDS:
            continue
        # A picture placeholder that *was* filled is a <p:pic> with no text
        # frame; one that was not is a <p:sp> with an empty one. So "no text
        # frame" means filled-with-something, and only an empty text frame is
        # the ghost we are after.
        if shape.has_text_frame and not shape.text_frame.text.strip():
            element = shape.element
            element.getparent().remove(element)
            removed += 1
    return removed


# ── shape drawing ────────────────────────────────────────────────────────────
def add_text(
    slide,
    blocks: list[tuple],
    box: tuple[float, float, float, float] | None = None,
    *,
    color: RGBColor | None,
    center: bool = False,
    middle: bool = False,
    into=None,
    shrink: bool = True,
    levels: list[int] | None = None,
    plain: list[bool] | None = None,
) -> None:
    """Overlay a text box. *blocks* = list of (text, pt_size, bold, font).

    With *into* set to an existing shape (a cloned placeholder), writes into
    that shape instead of adding a new one, and ignores *box* — the shape's own
    geometry is the designer's and is already what *box* was derived from.

    A ``None`` size, weight, face or *color* is **not written**, so the run
    inherits it from the template (see :func:`declared_style`): that is how
    ``--min-pt`` keeps a designer's 30 pt body instead of overwriting it.
    *shrink* allows the renderer to shrink text to fit its shape; off under
    ``--min-pt``, where shrinking is exactly what the floor forbids.
    *levels* sets each paragraph's list depth and *plain* marks paragraphs
    that must not get the placeholder's bullet glyph (prose, numbered items).
    """
    if into is not None:
        tf = into.text_frame
        tf.clear()  # a cloned placeholder arrives with one empty paragraph
    else:
        left, top, width, height = (Inches(v) for v in box or (0.0, 0.0, 1.0, 1.0))
        tf = slide.shapes.add_textbox(left, top, width, height).text_frame
    tf.word_wrap = True
    # With shrinking allowed: belt-and-braces against overflow, the renderer
    # auto-shrinks the run rather than clip it. Without: NONE is written
    # explicitly, overriding a normAutofit the layout's bodyPr may carry.
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE if shrink else MSO_AUTO_SIZE.NONE
    if middle:
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, (text, size, bold, font) in enumerate(blocks):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = text
        if levels is not None and i < len(levels) and levels[i]:
            p.level = levels[i]
        if plain is not None and i < len(plain) and plain[i]:
            # An explicit <a:buNone/>: a designer body placeholder bullets
            # every paragraph, and a sentence is not a list item.
            ppr = p._p.get_or_add_pPr()  # noqa: SLF001
            if ppr.find(_qa("buNone")) is None:
                ppr.append(ppr.makeelement(_qa("buNone"), {}))
        if into is None or size is not None:
            p.space_after = Pt(6)
        if center:
            p.alignment = PP_ALIGN.CENTER
        # Set on the RUN, not the paragraph: LibreOffice/PowerPoint read
        # run-level rPr for size/bold/font/colour, so a paragraph-level
        # default here would silently not render in at least one of the two.
        for run in p.runs:
            if size is not None:
                run.font.size = Pt(size)
            if bold is not None:
                run.font.bold = bold
            if font is not None:
                run.font.name = font
            if color is not None:
                run.font.color.rgb = color


def _fit(pic, max_w: float, max_h: float, cx: float, area_top: float) -> None:
    """Contain-fit *pic* inside (max_w x max_h) inches, centred at *cx*."""
    # min(), not a 1.0-capped scale: a small source image is GROWN to fill
    # its box rather than left tiny — deliberate, matches the eyeball loop's
    # own "image_too_small" check, which exists precisely to catch the
    # opposite mistake (a good source image rendered needlessly small).
    scale = min(Inches(max_w) / pic.width, Inches(max_h) / pic.height)
    pic.width = int(pic.width * scale)
    pic.height = int(pic.height * scale)
    pic.left = Inches(cx) - pic.width // 2
    pic.top = Inches(area_top) + (Inches(max_h) - pic.height) // 2


def add_image(slide, img: Path, *, box: tuple[float, float, float, float], alt: str = "") -> None:
    left, top, width, height = box
    cx = left + width / 2
    pic = slide.shapes.add_picture(str(img), Inches(left), Inches(top))
    _fit(pic, width, height, cx, top)
    if alt:
        # OOXML keeps a picture's accessible description in cNvPr/@descr.
        # python-pptx exposes no setter, so write the attribute: it is the same
        # one PowerPoint's own "Alt Text" pane edits, and the same one Pandoc
        # fills from Markdown alt text on the path this assembler bypasses.
        #
        # Always overwrite rather than only filling a blank: python-pptx
        # defaults descr to the image's FILE NAME, so a screen reader would
        # otherwise announce "chart dot png" — worse than silence, and a
        # default no caller asked for.
        pic._element._nvXxPr.cNvPr.set("descr", alt)  # noqa: SLF001


def add_code(
    slide,
    code: str,
    box: tuple[float, float, float, float],
    *,
    font: str,
    size: float = 13,
    shrink: bool = True,
) -> None:
    """A dark rounded panel holding *code*, every line of it.

    It used to keep the first twelve lines and drop the rest unannounced; a
    long listing now shrinks to fit (or, under ``--min-pt``, overruns and is
    reported by the audit) instead of being cut.
    """
    left, top, width, height = box
    rect = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height)
    )
    rect.fill.solid()
    rect.fill.fore_color.rgb = _CODE_BG
    rect.line.fill.background()
    rect.shadow.inherit = False
    tf = rect.text_frame
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE if shrink else MSO_AUTO_SIZE.NONE
    tf.margin_left = tf.margin_right = Inches(0.25)
    for i, ln in enumerate(code.splitlines()):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = ln or " "
        run = p.runs[0]
        run.font.name = font
        run.font.size = Pt(size)
        run.font.color.rgb = _CODE_FG


def add_table(
    slide,
    rows: list[list[str]],
    box: tuple[float, float, float, float],
    *,
    size: float | None,
    font: str | None,
) -> None:
    """A real PowerPoint table for a Markdown pipe table.

    Tables used to vanish from smart-layout slides: the text parser skipped
    every ``|`` row and no branch placed them. The template's default table
    style supplies colours; only the size (and the face) is set here.
    """
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    left, top, width, height = box
    shape = slide.shapes.add_table(
        len(rows), ncols, Inches(left), Inches(top), Inches(width), Inches(height)
    )
    for r, row in enumerate(rows):
        for c in range(ncols):
            cell = shape.table.cell(r, c)
            cell.text = row[c] if c < len(row) else ""
            for paragraph in cell.text_frame.paragraphs:
                for run in paragraph.runs:
                    if size is not None:
                        run.font.size = Pt(size)
                    if font is not None:
                        run.font.name = font


# ── assembly ──────────────────────────────────────────────────────────────────
@dataclass
class AssembleResult:
    pptx_path: Path
    placed: int
    total: int
    #: How many of the placed slides were carried by Seam E — cloned from one
    #: of the designer's own example pages rather than built on a bare layout.
    #: Always ``0`` unless ``reference_slides=True``, and never all of them:
    #: a page that cannot carry its content is refused, not forced.
    cloned: int = 0
    #: Slide index -> the example page that carried it, for the slides Seam E
    #: took. Reported rather than written back onto the ``Slide`` models, so
    #: assembly stays a pure function of them; it is what lets the eyeball loop
    #: judge a cloned slide against *the page it was cloned from* and move it
    #: to another one. See :func:`eyeball_slides`.
    pages: dict[int, int] = field(default_factory=dict)
    #: Slides the eyeball loop's vision judge gave no verdict on (timeout,
    #: empty or unparseable reply) on its last pass. Their verdict fell back
    #: to the measured audit alone; listed so "no complaint" is never mistaken
    #: for "approved".
    unjudged: list[int] = field(default_factory=list)


RenderMermaidFn = Callable[[str], "Path | None"]


def _finish(slide, s: Slide) -> None:
    """Close out a slide, whichever seam built it: notes, then ghost sweep."""
    if s.notes:
        # Notes exist precisely so this text is NOT on the slide; the notes
        # pane is the one place it belongs. `notes_slide` creates the notes
        # slide (and a default notes master) on first access.
        # One paragraph per bullet / paragraph, nested items indented: a
        # telegraphic script stays scannable mid-talk (notes_paragraphs).
        frame = slide.notes_slide.notes_text_frame
        paragraphs = notes_paragraphs(s.notes) or [(s.notes.strip(), 0)]
        frame.text = paragraphs[0][0]
        frame.paragraphs[0].level = paragraphs[0][1]
        for text, level in paragraphs[1:]:
            para = frame.add_paragraph()
            para.text = text
            para.level = level
    # Last, so "empty" means "nothing was placed in it by any branch" — and on
    # a Seam-E clone, "nothing the designer wrote survived in it either".
    ghosts = drop_empty_placeholders(slide)
    if ghosts:
        logger.debug("slide %d: dropped %d unfilled placeholder(s)", s.index, ghosts)


#: Slide placeholder kinds that take body text (``obj`` is OOXML's generic
#: content placeholder: "Title and Content"'s big box).
_BODY_PH_KINDS = {"body", "obj"}
_SUBTITLE_PH_KINDS = {"subTitle", "body", "obj"}


def _area(shape) -> int:
    try:
        return int(shape.width or 0) * int(shape.height or 0)
    except Exception:  # noqa: BLE001 — inherited geometry python-pptx cannot read
        return 0


def _ph_box(shape) -> tuple[float, float, float, float] | None:
    try:
        vals = (shape.left, shape.top, shape.width, shape.height)
    except Exception:  # noqa: BLE001
        return None
    if None in vals:
        return None
    return tuple(v / EMU_PER_INCH for v in vals)  # type: ignore[return-value]


def _hsplit(
    box: tuple[float, float, float, float], parts: int, gap: float = 0.3
) -> list[tuple[float, float, float, float]]:
    """*box* cut into *parts* side-by-side columns with a *gap* (inches)."""
    left, top, width, height = box
    each = (width - gap * (parts - 1)) / parts
    return [(left + k * (each + gap), top, each, height) for k in range(parts)]


def _intersects(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    """Whether two (left, top, width, height) boxes share any area."""
    return min(a[0] + a[2], b[0] + b[2]) > max(a[0], b[0]) and min(a[1] + a[3], b[1] + b[3]) > max(
        a[1], b[1]
    )


def _column_boxes(
    prs: Presentation, info: LayoutInfo | None, n: int
) -> list[tuple[float, float, float, float]]:
    """One box per column: the layout's own body boxes when it has *n*, else a split."""
    if info is not None:
        boxes = [
            ph.emu
            for ph in info.placeholders
            if ph.kind in _BODY_KINDS | {"obj"} and ph.emu is not None
        ]
        if len(boxes) >= n:
            # The n largest, read left to right: on a "Comparison" layout the
            # small header boxes lose to the two content boxes under them.
            biggest = sorted(boxes, key=lambda b: -b[2] * b[3])[:n]
            return [tuple(v / EMU_PER_INCH for v in b) for b in sorted(biggest, key=lambda b: b[0])]
    return _hsplit(content_box(prs, info), n)


@dataclass
class _Typeset:
    """How one slide's text is sized and coloured (see :func:`assemble`)."""

    min_pt: float | None
    fd: int
    fg: RGBColor

    def size(self, base: float, declared: float | None, *, inherit_ok: bool) -> float | None:
        """The size to write, or ``None`` to inherit the template's.

        Without a floor: the assembler's own sizes, as always. With one, the
        designer's declared size wins whenever it clears the floor — inherited
        outright when writing into their placeholder untouched, written out
        when an overlay box cannot inherit it — and nothing goes under it.
        """
        if self.min_pt is None:
            return base + self.fd
        if declared is not None and declared >= self.min_pt:
            if inherit_ok and self.fd == 0:
                return None
            return max(self.min_pt, declared + self.fd)
        return max(self.min_pt, base + self.fd)

    def colour(self, declared: tuple, *, inherit_ok: bool) -> RGBColor | None:
        """The colour to write, or ``None`` to keep the template's.

        A colour the template declares for that text is the designer's and is
        kept as is: the slide's background alone says nothing of the panel a
        title may sit on (observed: a "contrast fix" turned a dark title on a
        light panel white). The audit judges the result. Undeclared, the
        foreground is computed from the background as before.
        """
        _size, rgb, has = declared
        if has:
            if inherit_ok:
                return None
            return rgb or self.fg
        return self.fg


_NO_STYLE = (None, None, False)


def _style_of(shape) -> tuple:
    if shape is None:
        return _NO_STYLE
    try:
        return declared_style(shape)
    except Exception:  # noqa: BLE001 — an exotic template must not cost the slide
        return _NO_STYLE


def _layout_ph(layout, kinds: set[str]):
    for shape in layout.placeholders:
        if placeholder_kind(shape) in kinds:
            return shape
    return None


def _write_items(
    slide,
    items: list[Item],
    *,
    ts: _Typeset,
    font: str,
    into=None,
    box=None,
    lead: list[tuple] | None = None,
) -> None:
    """Body text, into a designer placeholder (``into``) or an overlay *box*."""
    if into is not None:
        style = _style_of(into)
        size = ts.size(16, style[0], inherit_ok=True)
        add_text(
            slide,
            [(it.text, size, None, None if size is None else font) for it in items],
            color=ts.colour(style, inherit_ok=True),
            into=into,
            shrink=ts.min_pt is None,
            levels=[it.level for it in items],
            plain=[not it.bullet for it in items],
        )
        return
    style = _style_of(_layout_ph(slide.slide_layout, _BODY_PH_KINDS))
    size = ts.size(16, style[0], inherit_ok=False)
    colour = ts.colour(style, inherit_ok=False)
    blocks = list(lead or [])
    blocks += [
        (("   " * it.level) + (f"•  {it.text}" if it.bullet else it.text), size, False, font)
        for it in items
    ]
    if blocks:
        add_text(slide, blocks, box, color=colour, shrink=ts.min_pt is None)


def assemble(
    slides: list[Slide],
    catalog: list[LayoutInfo],
    template: Path,
    out_path: Path,
    *,
    image_base_dir: Path | None = None,
    render_mermaid: RenderMermaidFn | None = None,
    default_layout: str | None = None,
    reference_slides: bool = False,
    avoid_pages: dict[int, list[int]] | None = None,
    min_pt: float | None = None,
) -> AssembleResult:
    """Build a real ``.pptx`` directly on each slide's AI-selected layout.

    For every slide, instantiate ``slides[i].chosen_layout`` from *template*
    (falling back to *default_layout*, or the template's first layout, when
    the pick is missing or unknown) and overlay title/body/image/code content
    sized from that layout's own placeholder geometry when the catalog
    recorded one. Per-slide ``overrides`` (written by :func:`eyeball_slides`)
    bound font size and image growth. Every paragraph, table and code line
    of the slide is placed: nothing is trimmed to make it fit.

    With *reference_slides* set, each slide is first offered to **Seam E**
    (:mod:`md2star.pptx_clone`): when the chosen layout has an example page in
    the template that can carry this slide's content, that page is *cloned* and
    its text replaced, so the deck inherits the designer's decorative shapes
    and typography instead of only their background. A refusal (no suitable
    example, a chart on the page, fewer bullets than columns) falls straight
    through to the Seam-D path below, which can place anything.
    *avoid_pages* maps a slide index to example pages it may **not** use —
    what :func:`eyeball_slides` writes after a vision model has judged one of
    them not to be carrying that slide.

    With *min_pt* (the CLI's ``--min-pt``), no slide text is set under that
    size: body text goes **into** the layout's own body placeholders, keeping
    the size, colour, face and bullets the designer declared whenever they
    clear the floor; overlay text uses the declared size or the floor; and
    nothing is allowed to auto-shrink. Overflow is then the audit's to report
    and the eyeball loop's to fix by moving or splitting the slide.

    Returns
    -------
    AssembleResult
        The output path plus how many of the slides were placed without error
        (a per-slide exception is logged and skipped, never aborts the deck),
        and how many of those a cloned example page carried.
    """
    catalog_by_name = {c.name: c for c in catalog}
    prs = Presentation(str(template))
    layouts = layout_index(prs)
    have = set(layouts)
    fam = template_fonts(template)
    title_font, body_font = fam["display"], fam["body"]
    canvas = (prs.slide_width, prs.slide_height)
    used_pages: set[int] = set()
    if reference_slides:
        # Seam E reads the designer's example pages as it builds, so they
        # cannot be cleared up front the way Seam D clears them: snapshot them,
        # append our slides after them, drop them at the end.
        from . import pptx_clone as clone  # noqa: PLC0415 — one-way import, see pptx_clone

        examples = clone.example_slides(prs)
        originals = clone.template_slide_ids(prs)
    else:
        clone, examples, originals = None, {}, None
        clear_slides(prs)

    n = len(slides)
    placed = 0
    cloned = 0
    refused = avoid_pages or {}
    carried_by: dict[int, int] = {}
    fallback_name = default_layout if default_layout in have else next(iter(have), None)
    if fallback_name is None:
        raise ValueError(f"template {template} exposes no slide layouts")

    for s in slides:
        # A missing or hallucinated pick (select_layouts failed, or a caller
        # set chosen_layout by hand) still has to land on SOME real layout —
        # the deck must never lose a slide over a bad AI decision.
        name = s.chosen_layout if s.chosen_layout in have else fallback_name
        layout = layouts[name]
        info = catalog_by_name.get(name)
        # A layout with no resolvable one-colour background (``dark is
        # None``: a photo, nothing declared anywhere) is treated as light —
        # the master's own background is now part of the resolution, so this
        # is the rare case. Getting dark wrong is a correctness bug, not a
        # cosmetic one: white-on-white is invisible.
        dark = is_dark_layout(layout)
        fg = _WHITE if dark else _NEAR_BLACK

        body = s.body
        mer = parse_mermaid(body) if "mermaid" in s.features else None
        # code/img are only checked when there's no mermaid block, since a
        # mermaid fence would otherwise also match the generic code/image
        # patterns and steal the slide from its actual diagram branch.
        code = parse_code(body) if not mer else None
        img = parse_image(body, image_base_dir) if not mer else None
        table = parse_table(body) if "table" in s.features else []
        # Title-only is decided once, by segment (`Slide.title_only`): a cover,
        # closing or divider with nothing to place. A slide that carries
        # bullets is a content slide wherever it sits, so nothing on it is
        # lost to its position in the deck.
        title_only = s.title_only

        # `or` inside the list, not around it: a one-element list is truthy
        # even when that element is "", so the outer form never fired.
        title_lines = [_clean(s.title) or "(untitled)"]

        try:
            # Parsed INSIDE the try so a malformed override (e.g. a corrupt
            # eyeball-loop verdict) only drops this one slide, never the deck.
            ov = s.overrides or {}
            fd = int(ov.get("font_delta", 0))
            igrow = float(ov.get("img_grow", 0.0))
            ts = _Typeset(min_pt=min_pt, fd=fd, fg=fg)
            columns = [body_items(c) for c in split_columns(body)] if not title_only else []
            items = [] if title_only else body_items(body)
            bullets = [it.text for it in items]
            mpng = render_mermaid(mer) if (mer and render_mermaid) else None

            # ── Seam E: clone the designer's own example page, if one fits ──
            if clone is not None and info is not None and not code and not table:
                payload = clone.Content(
                    title=title_lines[0],
                    bullets=bullets,
                    image=mpng or img,
                    # Authored alt text first; failing that the slide's title,
                    # which is at least a true description of what is shown.
                    alt=parse_alt_text(body) or title_lines[0],
                )
                picked = clone.pick_example(
                    examples,
                    info.example_pages,
                    payload,
                    used=used_pages,
                    canvas=canvas,
                    avoid=refused.get(s.index, ()),
                )
                if picked is not None:
                    page, example = picked
                    cloned_slide = clone.compose(
                        prs, example, payload, font_delta=fd, min_pt=min_pt
                    )
                    if cloned_slide is not None:
                        used_pages.add(page)
                        carried_by[s.index] = page
                        _finish(cloned_slide, s)
                        placed += 1
                        cloned += 1
                        logger.debug(
                            "slide %d: cloned example page %d of layout %r", s.index, page, name
                        )
                        continue
                    logger.debug("slide %d: example page %d declined it", s.index, picked[0])

            # ── Seam D: build on the bare layout (always able to place) ──
            slide = prs.slides.add_slide(layout)
            _build(
                prs,
                slide,
                s,
                info,
                ts,
                title=title_lines[0],
                title_only=title_only,
                items=items,
                columns=columns,
                visual=(mpng, img, code, table),
                igrow=igrow,
                fonts=(title_font, body_font, fam.get("family", "Consolas")),
            )
            _finish(slide, s)
            placed += 1
        except Exception as exc:  # noqa: BLE001 — one bad slide must not sink the deck
            logger.warning("slide %d (layout %r) failed to assemble: %s", s.index, name, exc)

    if originals is not None:
        # The designer's example pages were kept this long only so Seam E could
        # read them; what ships is what the build appended.
        clone.drop_template_slides(prs, originals)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_path))
    # The clone count only means something when Seam E was in play; on the
    # default path it would just be a zero nobody asked about.
    detail = f" ({cloned} from the template's own pages)" if reference_slides else ""
    logger.info("assembled %d/%d slides%s -> %s", placed, n, detail, out_path)
    return AssembleResult(
        pptx_path=out_path, placed=placed, total=n, cloned=cloned, pages=carried_by
    )


def _build(
    prs,
    slide,
    s: Slide,
    info: LayoutInfo | None,
    ts: _Typeset,
    *,
    title: str,
    title_only: bool,
    items: list[Item],
    columns: list[list[Item]],
    visual: tuple,
    igrow: float,
    fonts: tuple[str, str, str],
) -> None:
    """Seam D for one slide: title, then text and/or the one visual it carries."""
    title_font, body_font, mono = fonts
    mpng, img, code, table = visual
    # The slide's *own* cloned title placeholder, when the layout has one. See
    # the reconciliation note above: this is what puts the title in the
    # outline pane and the screen-reader reading order.
    title_ph = slide_placeholder(slide, TITLE_KINDS)
    t_style = _style_of(title_ph)
    # Inheriting the designer's whole title look (size, weight, face, colour,
    # alignment) is what --min-pt asks for; without it the assembler keeps
    # forcing its own, as it always has.
    inherit = ts.min_pt is not None and title_ph is not None

    def put_title(base: float, box, *, divider: bool = False) -> None:
        size = ts.size(base, t_style[0], inherit_ok=title_ph is not None)
        add_text(
            slide,
            [(title, size, None if inherit else True, None if inherit else title_font)],
            box,
            color=ts.colour(t_style, inherit_ok=title_ph is not None),
            center=divider and not inherit,
            middle=divider and not inherit,
            into=title_ph,
            shrink=ts.min_pt is None,
        )

    if title_only:
        # A cover, closing or divider: the title, and its subtitle when it has
        # one — on the layout's own subtitle zone, else just under the title.
        tbox = title_box(prs, info, divider=True)
        put_title(40, tbox, divider=True)
        if s.subtitle:
            lines = [Item(line, 0, False) for line in s.subtitle.splitlines() if line.strip()]
            sub_ph = next(
                (
                    ph
                    for ph in slide.placeholders
                    if placeholder_kind(ph) in _SUBTITLE_PH_KINDS and ph is not title_ph
                ),
                None,
            )
            if sub_ph is not None:
                style = _style_of(sub_ph)
                size = ts.size(20, style[0], inherit_ok=True)
                add_text(
                    slide,
                    [(it.text, size, None, None if size is None else body_font) for it in lines],
                    color=ts.colour(style, inherit_ok=True),
                    into=sub_ph,
                    shrink=ts.min_pt is None,
                    plain=[True] * len(lines),
                )
            else:
                left, top, width, height = tbox
                slide_h = prs.slide_height / EMU_PER_INCH
                below = (
                    left,
                    top + height,
                    width,
                    max(0.6, min(height * 0.6, slide_h - top - height)),
                )
                size = ts.size(20, None, inherit_ok=False)
                add_text(
                    slide,
                    [(it.text, size, False, body_font) for it in lines],
                    below,
                    color=ts.fg,
                    center=True,
                    shrink=ts.min_pt is None,
                )
        return

    has_visual = mpng is not None or img is not None or bool(code) or bool(table)
    body_phs = sorted(
        (
            ph
            for ph in slide.placeholders
            if placeholder_kind(ph) in _BODY_PH_KINDS and ph is not title_ph
        ),
        key=lambda ph: -_area(ph),
    )
    use_ph = ts.min_pt is not None and bool(body_phs)
    text = bool(items)
    # Where an overlay goes: the slide's own body placeholder when it has one
    # (its real geometry), else what the catalog recorded. The catalog reads
    # the designer's example page, whose biggest text may be the very zone
    # the title placeholder occupies — observed as a body box laid exactly
    # over the title on a "Big Number" layout.
    real = _ph_box(body_phs[0]) if body_phs else None
    cbox_default = real or content_box(prs, info)

    # ── title ──
    if title_ph is None and text and not has_visual and not columns:
        # No title zone: the heading shares the body box, which is what the
        # fit model measured (pptx_fit: "the heading will share the body box").
        lead = [(title, ts.size(26, None, inherit_ok=False), True, title_font)]
        if use_ph:
            put_title(26, title_box(prs, info))
            lead = []
        _write_items(
            slide,
            items,
            ts=ts,
            font=body_font,
            into=body_phs[0] if use_ph else None,
            box=cbox_default,
            lead=lead,
        )
        return
    base_title = 26 if text else (22 if code else 20)
    put_title(base_title, title_box(prs, info))

    # ── text regions ──
    vis_box = None
    if columns:
        # Text written outside the column divs (a lead sentence) heads the
        # first column rather than being lost or laid over the title.
        inside = {c.text for col in columns for c in col}
        outside = [it for it in items if it.text not in inside]
        if outside:
            columns = [outside + columns[0], *columns[1:]]
        if use_ph and len(body_phs) >= len(columns):
            targets = sorted(body_phs[: len(columns)], key=lambda ph: ph.left or 0)
            for col, ph in zip(columns, targets, strict=False):
                _write_items(slide, col, ts=ts, font=body_font, into=ph)
        else:
            real_cols = sorted(body_phs[: len(columns)], key=lambda ph: ph.left or 0)
            boxes = (
                [_ph_box(ph) for ph in real_cols]
                if len(real_cols) >= len(columns) and all(_ph_box(ph) for ph in real_cols)
                else _column_boxes(prs, info, len(columns))
            )
            for col, box in zip(columns, boxes, strict=False):
                _write_items(slide, col, ts=ts, font=body_font, box=box)
    elif text:
        has_pic = info is not None and any(ph.kind in _IMAGE_KINDS for ph in info.placeholders)
        if use_ph:
            target = body_phs[0]
            if has_visual:
                # Text and a visual: the designer's body box keeps the left
                # part, the visual takes the right.
                full = _ph_box(target)
                if full is not None:
                    text_box, vis_box = _hsplit(full, 2)
                    target.left, target.top = Inches(text_box[0]), Inches(text_box[1])
                    target.width, target.height = Inches(text_box[2]), Inches(text_box[3])
            _write_items(slide, items, ts=ts, font=body_font, into=target)
        else:
            cbox = cbox_default
            picture = mpng is not None or img is not None
            # The layout's own picture zone is used only when it leaves the
            # text box alone: a demo page's picture region laid over a
            # full-width default text box put a painting on the words.
            clear = picture and has_pic and not _intersects(cbox, image_box(prs, info))
            if has_visual and not clear:
                text_box, vis_box = _hsplit(cbox, 2)
            else:
                text_box = cbox
            _write_items(slide, items, ts=ts, font=body_font, box=text_box)
    elif use_ph and has_visual:
        vis_box = _ph_box(body_phs[0])

    # ── the visual ──
    if mpng is not None or img is not None:
        left, top, width, height = vis_box or image_box(prs, info)
        add_image(
            slide,
            mpng if mpng is not None else img,
            box=(left - igrow, top, width + 2 * igrow, height + igrow),
            # A rendered diagram's accessible description is the slide's own
            # title: nothing else here knows what the graph says. A picture
            # keeps its authored alt text when it has one.
            alt=title if mpng is not None else (parse_alt_text(s.body) or title),
        )
    elif code:
        lines = code.count("\n") + 1
        if lines > 12:
            logger.warning("slide %d: %d-line code block; consider splitting it", s.index, lines)
        add_code(
            slide,
            code,
            vis_box or content_box(prs, info),
            font=mono,
            size=ts.size(13, None, inherit_ok=False),
            shrink=ts.min_pt is None,
        )
    elif table:
        add_table(
            slide,
            table,
            vis_box or content_box(prs, info),
            size=ts.size(14, None, inherit_ok=False),
            font=body_font,
        )


# ── target-matching Ralph Eyeball Loop ───────────────────────────────────────
_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "matches": {"type": "boolean"},
        "overflow": {"type": "boolean"},
        "low_contrast": {"type": "boolean"},
        "too_empty": {"type": "boolean"},
        "image_too_small": {"type": "boolean"},
        "discrepancies": {"type": "string"},
    },
    "required": ["matches"],
}

_JUDGE_PROMPT = (
    "The FIRST image is the TARGET: an example slide of the designer template "
    "layout this slide is supposed to use. The SECOND image is the CANDIDATE: "
    "this slide as actually rendered. Judge the candidate against the target's "
    "composition, not its specific words/pictures: does it place a title, body "
    "and any image/diagram in similarly proportioned regions, with nothing "
    "overflowing the slide edges, clipped, low-contrast against its background, "
    "or leaving an awkward empty void? Reply as JSON: matches (true only if it "
    "is clean and well-composed), overflow, low_contrast, too_empty, "
    "image_too_small, and a short discrepancies string (empty if matches)."
)


#: The judge for a **cloned** slide (Seam E). Its target is not a cousin of the
#: candidate but the very page the candidate was built from, so the question
#: stops being "do these two compositions rhyme?" and becomes the much sharper
#: "did replacing the content break anything?". Same schema, so the verdict
#: feeds the same bounded fixes.
_CLONE_JUDGE_PROMPT = (
    "The FIRST image is the TARGET: a page of the designer's own template, "
    "carrying their placeholder text and their stock photographs. The SECOND "
    "image is the CANDIDATE: that same page rebuilt with a real deck's "
    "content. Their words are meant to be gone and their stock photographs are "
    "meant to be replaced or absent — never report those as missing, and never "
    "ask for a picture the candidate was not given. Judge only what the "
    "rebuild did to the design: text overflowing its shape, clipped at an "
    "edge, or running into another shape; a picture that is distorted or so "
    "small in its slot that it reads as lost; text you cannot read against "
    "what is behind it; or a page so bare that the composition has visibly "
    "collapsed. Point at the defect or do not report it: when nothing of the "
    "kind is visible, matches is true. Reply as JSON: matches, overflow, "
    "low_contrast, too_empty, image_too_small, and a short discrepancies "
    "string (empty if matches)."
)


#: What a model-free finding means in the verdict vocabulary the loop already
#: speaks. ``overlap`` and ``ghost-placeholder`` are deliberately absent: the
#: first is usually a designer's composition and the second is swept at
#: assembly, so neither is something the loop's bounded fixes can improve.
_FINDING_FLAGS = {
    "overrun": "overflow",
    "off-slide": "overflow",
    "illegible-type": "overflow",
    # Measured, and the one verdict this loop has always been able to report
    # and never able to fix: no font size or bullet count makes grey legible on
    # grey. `_overrides_for` deliberately has nothing for it, which is what
    # sends the slide down the ladder to a box with a different colour behind
    # it — another of the designer's pages, then another layout.
    "low-contrast": "low_contrast",
    # Only reported under --min-pt: type under the floor is never fixed by a
    # font nudge, so it reads as an overflow that is beyond shrinking.
    "under-min-pt": "overflow",
}


def _measured_verdict(findings: list, index: int) -> dict | None:
    """The deterministic half of the Look step: what arithmetic already knows.

    :mod:`md2star.pptx_audit` measures the saved deck — text that needs more
    room than its box gives it, a shape past the canvas, type under the
    legibility floor — and says so with the number in it. That is strictly
    better evidence than a vision model's opinion on exactly those questions,
    and it costs nothing: no render, no model, no network. Turning it into a
    verdict lets the loop act on it with the fixes it already has, and lets it
    run at all on a machine with no VLM.
    """
    mine = [f for f in findings if f.slide == index and f.kind in _FINDING_FLAGS]
    if not mine:
        return None
    verdict: dict = {"matches": False, "discrepancies": "; ".join(str(f) for f in mine)}
    for finding in mine:
        verdict[_FINDING_FLAGS[finding.kind]] = True
    if any(f.kind == "under-min-pt" for f in mine):
        verdict["beyond_shrinking"] = True
    # An overrun is the one finding that comes with its own answer: the audit
    # has already computed the size that *would* fit. Two things follow, and
    # both are better than the blind nudge a vision model's "it overflows"
    # can earn.
    # Function-level, like every other reference to the audit from here: it
    # imports this module for its placeholder vocabulary, so the one-way rule
    # is what keeps the pair from forming a cycle.
    from .pptx_audit import LEGIBLE_MIN_PT  # noqa: PLC0415

    sized = [f for f in mine if f.fits_pt and f.measured_pt]
    if sized:
        worst = min(sized, key=lambda f: f.fits_pt)
        if worst.fits_pt < LEGIBLE_MIN_PT:
            # No amount of shrinking wins this one: at the size that would fit,
            # nobody in the room can read it. Say so, so the ladder skips the
            # font nudge and goes looking for a box that is actually big enough
            # — another of the designer's pages, or another layout.
            verdict["beyond_shrinking"] = True
        else:
            # Exactly the correction, in one shot. The loop still never
            # searches; it simply no longer has to guess the step.
            verdict["font_delta"] = int(worst.fits_pt - worst.measured_pt)
    return verdict


def _merged_verdict(measured: dict | None, judged: dict | None) -> dict | None:
    """Combine the measured verdict with the model's, arithmetic winning.

    A vision model looking at a render cannot see an overrun — the renderer has
    already hidden it by shrinking the type, which is the whole reason the
    audit reports it with the size that *would* fit. So a measurement never
    loses to an opinion: anything the audit flagged stays flagged.
    """
    if measured is None:
        return judged
    if judged is None:
        return measured
    # Everything the measurement actually says, not only its True flags: the
    # exact font delta it computed is an int, and dropping it here is how a
    # slide that had a precise answer ends up with the model's blind -4pt.
    informative = {k: v for k, v in measured.items() if v not in (None, False, "")}
    merged = {**judged, **informative}
    merged["matches"] = False
    merged["discrepancies"] = "; ".join(
        part for part in (measured.get("discrepancies"), judged.get("discrepancies")) if part
    )
    return merged


#: The smallest type the assembler sets on a content slide — its bullets. A
#: ``font_delta`` is one number applied to *every* size on the slide, so this
#: is the one that binds: a delta computed from an overrunning 26 pt title
#: would take 16 pt bullets to 8 pt, which the audit then reports as illegible
#: (observed, on a real deck, from the first version of the exact correction).
SMALLEST_BASE_PT = 16


def _overrides_for(
    verdict: dict, current: dict | None = None, *, min_pt: float | None = None
) -> dict:
    """The bounded fix for one verdict, *accumulated* onto the slide's *current* one.

    Bounded, one-shot corrections — never a search: a font step and +50%
    image growth are each a single fixed nudge per flagged issue, not a tuned
    parameter the loop iterates toward. low_contrast/too_empty are reported
    to the caller in ``discrepancies`` but have no safe automatic fix here (a
    layout swap, not a font tweak, is what they need).

    ``font_delta`` is relative to the slide's **original** sizes. A measured
    step is computed from the size the slide has *now* (already shrunk by an
    earlier pass), so it is added to the current delta; replacing it, as the
    loop used to, undid the first pass's shrink on the second.

    Under *min_pt* no overflow is ever fixed by shrinking: the empty answer
    sends the slide down the ladder to a roomier layout, or to a split. And no
    fix ever drops content: the old "keep two bullets" override is gone.
    """
    from .pptx_audit import LEGIBLE_MIN_PT  # noqa: PLC0415 — one-way, see above

    ov: dict = {}
    if verdict.get("beyond_shrinking"):
        # Measured, and measured as unwinnable by type size: leaving this
        # empty is what lets the caller's ladder move the slide instead.
        return ov
    if verdict.get("overflow"):
        if min_pt is not None:
            return ov
        # The measured eye knows the exact step (see _measured_verdict); the
        # model's eye only knows that something overflowed, and -4pt is the
        # nudge it has always earned.
        delta = int((current or {}).get("font_delta", 0)) + int(verdict.get("font_delta", -4))
        if SMALLEST_BASE_PT + delta < LEGIBLE_MIN_PT:
            # The correction would make the smallest type on the slide
            # unreadable, which is not a correction. Same answer as
            # `beyond_shrinking`, reached from the other direction: nothing
            # here fixes it, so let the ladder go find a bigger box.
            return ov
        ov["font_delta"] = delta
    if verdict.get("image_too_small"):
        ov["img_grow"] = 0.5
    return ov


def _reselect(s: Slide) -> str | None:
    """Move a slide to the next layout its content can actually live on.

    The loop's other levers -- font_delta, bullets, img_grow -- all assume the
    layout was right and the content merely needs trimming to sit on it. When
    the verdict is `too_empty`, or when overflow is bad enough that shrinking
    by 4pt will not close it, that assumption is the thing that is wrong: the
    slide is on a layout it should never have been given, and nudging type
    size polishes a decision instead of revisiting it.

    This module already said so, in the comment above `_overrides_for`: those
    verdicts "need a layout swap, not a font/bullet tweak". This is that swap.

    Returns the name of the next-best fitting layout, or ``None`` when there
    is no better option -- in which case the caller keeps the current pick and
    the existing "no automatic fix applies" path reports it.
    """
    ranked = getattr(s, "fit_ranked", None)
    if not ranked:
        return None
    current = s.chosen_layout
    tried = set(getattr(s, "tried_layouts", ()) or ())
    for layout, report in ranked:
        if not report.fits or report.overruns:
            continue
        if layout.name == current or layout.name in tried:
            continue
        return layout.name
    return None


def eyeball_slides(
    slides: list[Slide],
    catalog: list[LayoutInfo],
    template: Path,
    out_path: Path,
    *,
    indices: list[int] | None = None,
    max_iterations: int = 1,
    chat: ChatFn | None = None,
    render_template: RenderFn | None = None,
    render_deck: Callable[[Path], dict[int, bytes]] | None = None,
    image_base_dir: Path | None = None,
    render_mermaid: RenderMermaidFn | None = None,
    default_layout: str | None = None,
    allow_reselect: bool = True,
    reference_slides: bool = False,
    min_pt: float | None = None,
) -> AssembleResult:
    """Target-matching Ralph Eyeball Loop over an assembled deck.

    Assembles (or re-uses an already-assembled) deck, renders it, and for each
    of *indices* (default: every slide) shows a vision model both the
    candidate render and the chosen layout's own catalog thumbnail. On a
    mismatch it writes a bounded ``overrides`` entry back onto the slide
    (shrink text, cap bullets, grow an undersized image — never touches the
    picture itself) and re-assembles, up to *max_iterations* passes. Any
    transport/render failure leaves the current best assembly untouched.

    With *reference_slides* on, the loop gets sharper on both ends. Its
    **target** for a cloned slide is the designer page that slide was cloned
    from rather than the layout's representative thumbnail — the tightest
    comparison available, since the candidate is literally that page with the
    deck's own content in it. And it gains a **fix it did not have**: when a
    cloned slide is flagged and no bounded override applies, it moves the slide
    to a *different example page of the same layout* before considering a
    layout swap. A designer who demonstrated one layout five ways has given
    five compositions to try, and reaching for another of theirs is a smaller,
    truer correction than abandoning the layout they chose. If none of the
    remaining pages can carry the slide, assembly falls back to Seam D on its
    own, which is the safe generic this loop has always wanted.

    A judge that times out or answers nothing is **unknown**, not "matches":
    the slide is judged on the measured audit alone and listed in
    :attr:`AssembleResult.unjudged`.

    With *min_pt*, an overflow is never fixed by shrinking: the slide moves to
    the next layout that holds it at the floor, and when none is left it is
    split in two (continuation titled "(suite)" / "(cont.)").

    *render_deck* renders the assembled output deck itself (default:
    :func:`md2star.pptx_layout.render_deck_pages`, LibreOffice + poppler);
    injectable so the loop is testable offline without either installed.
    """
    chat = chat or default_chat(kind="vlm")
    render_template = render_template or default_render()
    render_deck = render_deck or render_deck_pages
    catalog_by_name = {c.name: c for c in catalog}
    target_indices = indices if indices is not None else [s.index for s in slides]
    by_index = {s.index: s for s in slides}
    # Example pages a verdict has already rejected, per slide. Grows only, so
    # the loop can never return to a page it has judged and moved off.
    refused_pages: dict[int, list[int]] = {}

    result = assemble(
        slides,
        catalog,
        template,
        out_path,
        image_base_dir=image_base_dir,
        render_mermaid=render_mermaid,
        default_layout=default_layout,
        reference_slides=reference_slides,
        avoid_pages=refused_pages,
        min_pt=min_pt,
    )

    # One extra pass beyond max_iterations: the loop always re-judges after
    # the LAST fix is applied (to know whether it actually helped and to
    # report an accurate result), it just never applies a NEW fix on that
    # final pass — see the ``iteration < max_iterations`` guards below.
    # Imported here, not at module scope: the audit imports THIS module for its
    # placeholder vocabulary, and the one-way rule is what keeps that from
    # becoming a cycle (see md2star/pptx_audit.py's own note about it).
    from .pptx_audit import audit  # noqa: PLC0415

    for iteration in range(max_iterations + 1):
        pages = render_deck(out_path)
        # The Look step has two eyes. This one measures the file and is always
        # available — no render, no model, no network — so the loop still does
        # real work on a machine where the other one cannot open.
        measured = audit(out_path, min_pt=min_pt)
        flagged = 0
        unjudged: list[int] = []
        to_split: list[int] = []
        for i in target_indices:
            s = by_index.get(i)
            if s is None:
                continue
            verdict = _measured_verdict(measured, i)
            candidate_png = pages.get(i)
            info = catalog_by_name.get(s.chosen_layout) if s.chosen_layout else None
            # A cloned slide is judged against the page it was cloned from:
            # same composition, same decoration, only the words differ, so a
            # mismatch is about this slide rather than about the layout family.
            # Everything else keeps the layout's representative thumbnail.
            target_page = result.pages.get(i) or (info.rep_page if info else None)
            target_png = (
                render_template(template, target_page)
                if (candidate_png is not None and target_page is not None)
                else None
            )
            if target_png is not None:
                # A cloned slide is compared with its own source page, so it
                # gets the sharper question (see _CLONE_JUDGE_PROMPT);
                # everything else is still judged against a family resemblance.
                prompt = _CLONE_JUDGE_PROMPT if i in result.pages else _JUDGE_PROMPT
                out = chat(prompt, [target_png, candidate_png], _JUDGE_SCHEMA)
                judged = parse_json_reply(out)
                if not judged or "matches" not in judged:
                    # Timeout, empty or unparseable: UNKNOWN, not "matches".
                    # The slide is judged on the measured audit alone, and
                    # said so, rather than reading as a perfect deck.
                    judged = None
                    unjudged.append(i)
                    logger.info(
                        "eyeball loop: no verdict from the judge for slide %d; "
                        "using the measured audit only",
                        s.index,
                    )
                verdict = _merged_verdict(verdict, judged)
            if not verdict or verdict.get("matches"):
                continue
            if iteration < max_iterations:
                ov = _overrides_for(verdict, s.overrides, min_pt=min_pt)
                if ov:
                    # Merge, not replace: a slide flagged on two different
                    # passes accumulates both fixes instead of losing the first
                    # (font_delta is already the running total, see above).
                    s.overrides = {**(s.overrides or {}), **ov}
                    flagged += 1
                else:
                    # No pixel-level lever applies. The first thing to try is
                    # not a different layout but a different *page* of the one
                    # the designer already chose: they demonstrated it more
                    # than once, and each demonstration is a composition this
                    # slide can be rebuilt on. Smaller correction, truer to the
                    # template, and when no page is left assembly degrades to
                    # Seam D by itself.
                    if i in result.pages:
                        refused_pages.setdefault(i, []).append(result.pages[i])
                        logger.info(
                            "eyeball loop: slide %d — example page %d is not carrying it "
                            "(%s); trying another page of %s",
                            s.index,
                            result.pages[i],
                            verdict.get("discrepancies", "").strip() or "no discrepancy text",
                            s.chosen_layout,
                        )
                        # A fix tuned for the old page is wrong on a new one,
                        # exactly as it is after a layout swap.
                        s.overrides = {}
                        flagged += 1
                        continue
                    # Still nothing. Now consider that the layout itself may be
                    # the mistake: `too_empty` and an alignment discrepancy are
                    # both symptoms of content sitting somewhere it does not
                    # belong, and the comment above `_overrides_for` already
                    # says these "need a layout swap, not a font/bullet tweak".
                    #
                    # The geometric ranking computed at selection time is
                    # still on the slide, so the next-best host is known
                    # without another model call.
                    # A layout the author named is theirs: never swapped.
                    swap = _reselect(s) if allow_reselect and not s.pinned else None
                    if swap:
                        s.tried_layouts = [
                            *(getattr(s, "tried_layouts", None) or []),
                            s.chosen_layout,
                        ]
                        logger.info(
                            "eyeball loop: slide %d — %s is not carrying it (%s); moving to %s",
                            s.index,
                            s.chosen_layout,
                            verdict.get("discrepancies", "").strip() or "no discrepancy text",
                            swap,
                        )
                        s.chosen_layout = swap
                        s.chosen_why = "eyeball loop moved it here"
                        # A different layout invalidates fixes tuned for the
                        # old one: a -4pt that was right for a cramped box is
                        # wrong on a roomy one.
                        s.overrides = {}
                        flagged += 1
                    elif min_pt is not None and verdict.get("overflow"):
                        # No layout holds it at the floor: two slides do.
                        to_split.append(i)
                    else:
                        # Genuinely nothing left to try. Logged so this gap is
                        # visible instead of reading as "nothing to fix".
                        logger.info(
                            "eyeball loop: slide %d flagged (%s) but no automatic fix applies",
                            s.index,
                            verdict.get("discrepancies", "").strip() or "no discrepancy text",
                        )
        result.unjudged = unjudged
        if to_split and iteration < max_iterations:
            slides, by_index, target_indices, refused_pages = _apply_splits(
                slides, to_split, target_indices, refused_pages, explicit=indices is not None
            )
            flagged += len(to_split)
        if iteration < max_iterations:
            if not flagged:
                break  # nothing actionable left to fix — stop before a no-op re-assemble
            result = assemble(
                slides,
                catalog,
                template,
                out_path,
                image_base_dir=image_base_dir,
                render_mermaid=render_mermaid,
                default_layout=default_layout,
                reference_slides=reference_slides,
                avoid_pages=refused_pages,
                min_pt=min_pt,
            )

    result.unjudged = sorted(set(result.unjudged))
    return result


def _apply_splits(
    slides: list[Slide],
    to_split: list[int],
    targets: list[int],
    refused: dict[int, list[int]],
    *,
    explicit: bool,
):
    """Split each slide of *to_split* in two, in place, and renumber the deck.

    In place (``slides[:] = ...``) because the caller's list is the deck the
    pipeline reports on. Returns the refreshed index map, target list and
    refused-page map, all in the new numbering.
    """
    from .pptx_layout import _body_blocks, continuation_label, split_slide  # noqa: PLC0415

    label = continuation_label(slides[0].lang if slides else "", " ".join(x.body for x in slides))
    new: list[Slide] = []
    old_to_new: dict[int, list[int]] = {}
    for s in slides:
        heading, blocks = _body_blocks(s.body)
        parts = [s]
        if s.index in to_split and len(blocks) >= 2:
            half = (len(blocks) + 1) // 2
            parts = split_slide(s, [blocks[:half], blocks[half:]], heading, label)
            for p in parts:
                p.fit_ranked = s.fit_ranked
                p.tried_layouts = list(s.tried_layouts)
            logger.warning(
                "eyeball loop: slide %d (%r) overflows every layout at the floor; split in two",
                s.index,
                s.title,
            )
        elif s.index in to_split:
            logger.warning(
                "eyeball loop: slide %d (%r) overflows at the floor and has one block: shorten it",
                s.index,
                s.title,
            )
        old_to_new[s.index] = []
        for p in parts:
            new.append(p)
            old_to_new[s.index].append(len(new))
    for k, p in enumerate(new, start=1):
        p.index = k
    slides[:] = new
    by_index = {p.index: p for p in new}
    if explicit:
        targets = [j for i in targets for j in old_to_new.get(i, [])]
    else:
        targets = [p.index for p in new]
    refused = {old_to_new[i][0]: pages for i, pages in refused.items() if i in old_to_new}
    return slides, by_index, targets, refused
