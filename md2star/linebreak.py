"""Semantic line breaking: md2star chooses where a slide's lines end.

A renderer wraps greedily, so a line ends wherever the next word stops
fitting: on « de », on « the », before a lone « : », between « 500 » and
« 000 ». The usual cure, a no-break space, does not work on every template:
Satoshi, the course's face, has no glyph for U+00A0 or U+202F at all.

So when md2star writes a title or a paragraph into a box whose width and font
size it knows, it breaks the lines itself, with the face's real advance widths
(read from the font file's ``cmap`` and ``hmtx`` tables, 0.55 em per character
when the file cannot be found), and writes explicit line breaks the renderer
keeps. The break points are chosen by dynamic programming over a cost model:

* a line does not end on a function word (article, preposition, conjunction,
  pronoun, auxiliary — French and English) whenever any other break fits;
* a line never starts with ``: ; ? ! » %`` nor with a ``·`` separator, and a number is never separated
  from the number or the unit after it (500 000, 2 min, 30 %);
* no single orphan word on the last line;
* breaking after punctuation, or before a word that opens a clause (qui, que,
  pour, quand, mais, which, when, because), is preferred;
* among the permitted breaks, balanced lines win, and each extra line costs.

The cost model is the one the course's figures already use (``figkit.wrap``).
"""

from __future__ import annotations

import functools
import re
import struct
from pathlib import Path

#: Advance of one character when the face's own metrics cannot be read.
FALLBACK_EM = 0.55

#: Safety factor on measured widths: a renderer's kerning, hinting or a
#: slightly different inset must never make it re-wrap a line we broke.
WIDTH_MARGIN = 1.03

_FONT_DIRS = (
    Path.home() / "Library/Fonts",
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path.home() / ".local/share/fonts",
    Path.home() / ".fonts",
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
)

#: Words that announce what follows: a line ending on one reads as cut.
GLUE_AFTER = frozenset(
    """le la les l' l’ un une des de du d' d’ au aux à a en et ou ni que qu' qu’ qui ne n' n’
ce c' c’ cet cette ces son sa ses mon ma mes ton ta tes notre nos votre vos leur leurs se s' s’
sur sous dans par pour avec sans chez vers entre est sont être plus très pas y il elle on ils
elles nous vous je j' j’
the a an of to in on at by for and or nor with from as is are was be not no our your their
its his her my this that these those into than per via""".split()
)

#: Words that open a clause: breaking just before one reads naturally.
BREAK_BEFORE = frozenset(
    """qui que quand pour mais donc car si comme parce puis alors avant après où
which that when because but so if then while where""".split()
)

#: Characters a line must never start with.
NO_LINE_START = frozenset(":;?!»%)…")

#: Glyphs that separate two parts of a line, or open a bullet.
SEPARATORS = frozenset("•·")

#: Units that stay with the number before them.
UNITS = frozenset(
    "min h s ms pt kg g km m cm mm ans an mois jours j md mds m€ k€ € $ % x fois".split()
)

#: Every space a renderer might break at, or that a face may lack.
_NBSP = "   "


# ── font metrics ─────────────────────────────────────────────────────────────
def _metrics(path: Path) -> tuple[int, list[int], dict[int, int]]:
    """``(units per em, advance widths, codepoint → glyph id)`` of an OTF/TTF."""
    b = path.read_bytes()
    # The sfnt header: numTables sits at offset 4, and the table directory
    # starts at 12 with one 16-byte record (tag, checksum, offset, length) each.
    n = struct.unpack_from(">H", b, 4)[0]
    tables = {}
    for i in range(n):
        tag, _, off, ln = struct.unpack_from(">4sIII", b, 12 + 16 * i)
        tables[tag.decode("latin1")] = (off, ln)
    # unitsPerEm (head + 18) turns every advance into a fraction of the em.
    upm = struct.unpack_from(">H", b, tables["head"][0] + 18)[0]
    # numberOfHMetrics (hhea + 34): hmtx holds that many (advance, lsb) pairs;
    # glyphs past the last one reuse its advance, hence the clamp in width().
    n_hm = struct.unpack_from(">H", b, tables["hhea"][0] + 34)[0]
    hmtx = tables["hmtx"][0]
    adv = [struct.unpack_from(">H", b, hmtx + 4 * i)[0] for i in range(n_hm)]
    cmap = tables["cmap"][0]
    # Pick a Unicode subtable: Windows BMP (3, 1) is preferred and ends the
    # search; Unicode-platform 0/3 and 0/4 are kept as fallbacks if it is absent.
    sub = None
    for i in range(struct.unpack_from(">H", b, cmap + 2)[0]):
        pid, eid, off = struct.unpack_from(">HHI", b, cmap + 4 + 8 * i)
        if (pid, eid) in ((3, 1), (0, 3), (0, 4)):
            sub = cmap + off
            if (pid, eid) == (3, 1):
                break
    table: dict[int, int] = {}
    # Only format 4 (segment mapping to delta values) is decoded: it is the one
    # every Latin text face ships. Any other format leaves the table empty, and
    # width() then prices every character at the fallback em.
    if sub is not None and struct.unpack_from(">H", b, sub)[0] == 4:
        # segCountX2, then four parallel arrays: endCode, (a reserved pad),
        # startCode, idDelta, idRangeOffset, each segCountX2 bytes long.
        seg2 = struct.unpack_from(">H", b, sub + 6)[0]
        end_o = sub + 14
        start_o = end_o + seg2 + 2
        delta_o = start_o + seg2
        range_o = delta_o + seg2
        for s in range(seg2 // 2):
            end = struct.unpack_from(">H", b, end_o + 2 * s)[0]
            start = struct.unpack_from(">H", b, start_o + 2 * s)[0]
            delta = struct.unpack_from(">h", b, delta_o + 2 * s)[0]
            rng = struct.unpack_from(">H", b, range_o + 2 * s)[0]
            if start == 0xFFFF:
                continue  # the mandatory closing segment maps nothing
            for c in range(start, min(end, 0xFFFE) + 1):
                if rng == 0:
                    # Direct segment: the glyph id is the codepoint plus delta, mod 2^16.
                    gid = (c + delta) & 0xFFFF
                else:
                    # Indirect segment: idRangeOffset is a byte offset, counted from
                    # its own slot, into glyphIdArray; 0 there still means "no glyph".
                    gid = struct.unpack_from(">H", b, range_o + 2 * s + rng + 2 * (c - start))[0]
                    gid = (gid + delta) & 0xFFFF if gid else 0
                if gid:
                    table[c] = gid
    return upm, adv, table


@functools.lru_cache(maxsize=32)
def _face_file(family: str, bold: bool) -> Path | None:
    """The font file of *family* in that weight, from the usual font folders."""
    stem = family.replace(" ", "")
    weights = ("Bold", "SemiBold", "Medium") if bold else ("Regular", "Book", "Roman", "")
    names = [f"{stem}-{w}" if w else stem for w in weights]
    for folder in _FONT_DIRS:
        if not folder.is_dir():
            continue
        for name in names:
            for ext in (".otf", ".ttf"):
                hit = folder / f"{name}{ext}"
                if hit.is_file():
                    return hit
    return None


@functools.lru_cache(maxsize=32)
def face(family: str | None, bold: bool = False) -> tuple[int, list[int], dict[int, int]] | None:
    """The metrics of *family* (``None``: the 0.55 em fallback is used)."""
    if not family:
        return None
    path = _face_file(family, bold)
    if path is None:
        return None
    try:
        return _metrics(path)
    except Exception:  # noqa: BLE001 — a font we cannot parse is a font we do not have
        return None


def has_glyph(metrics, ch: str) -> bool:
    """Whether the face draws *ch* (always ``False`` without metrics)."""
    # Satoshi is the case in point: no U+00A0, no U+202F, so a no-break space
    # written into its box would render as a missing-glyph box or a fallback.
    return metrics is not None and ord(ch) in metrics[2]


def width(text: str, size: float, metrics=None) -> float:
    """Printed width of *text* at *size* pt, in points."""
    if metrics is None:
        return len(text) * size * FALLBACK_EM * WIDTH_MARGIN
    upm, adv, table = metrics
    total = 0.0
    for ch in text:
        gid = table.get(ord(ch))
        if gid is None and ch in _NBSP:
            # A face without a no-break space gets a plain one in break_lines(),
            # so measure it as what will actually be printed.
            gid = table.get(32)
        # Unknown glyph: price it at the fallback em rather than at zero, so a
        # missing character can only make a line look wider, never narrower.
        total += adv[min(gid, len(adv) - 1)] if gid is not None else FALLBACK_EM * upm
    return total * size / upm * WIDTH_MARGIN


# ── where a line may end ─────────────────────────────────────────────────────
def _is_number(word: str) -> bool:
    """Whether *word* is digits once its group separators are removed."""
    # « 1 000 », « 1,000 » and « 2.5 » all count: what matters is that the
    # next token (another group of digits, or a unit) must stay beside it.
    core = word
    for ch in _NBSP + " ,.":
        core = core.replace(ch, "")
    return core.isdigit()


def cost_break(left: str, right: str, *, first: bool = False) -> float:
    """Cost of ending a line on word *left* and starting the next on *right*.

    *first* says *left* opens the paragraph: a « • » or « · » there is a
    bullet and stays with its word; anywhere else it separates two parts
    (« S06 · L'IA générative ») and closes its line like punctuation.
    """
    lw = left.lower().strip('«“("')
    rw = right.lower().strip('»”)".,;:!?')
    if right[:1] in NO_LINE_START or right in ("%", "€", "$") or right in SEPARATORS:
        return 1e6  # « : », « % » or a « · » separator alone at the start of a line
    if left in SEPARATORS:
        return 1e6 if first else -40.0  # a bullet stays with its word; a separator ends a line
    if left[-1:] == "«" or left.endswith("“"):
        return 1e6  # an opening quote stays with its word
    if _is_number(left) and (right[:1].isdigit() or rw in UNITS):
        return 1e6  # 500 000, 2 min: a number and its unit stay together
    if lw in GLUE_AFTER or lw.endswith("'") or lw.endswith("’"):
        return 400.0  # ending a line on « de », « l' », « the »
    if left[-1:] in ",;:.!?)»" or left.endswith("…"):
        return -40.0  # after punctuation: natural
    if rw in BREAK_BEFORE:
        return -25.0  # before « qui », « pour »: the start of a group
    return 0.0


def wrap(text: str, size: float, max_w: float, metrics=None) -> list[str]:
    """*text* broken into lines no wider than *max_w* points at *size* pt.

    A word wider than the box alone gets a line of its own (the renderer will
    break it; nothing better exists). Existing newlines are kept.
    """
    out: list[str] = []
    for para in text.split("\n"):
        lead = para[: len(para) - len(para.lstrip(" "))]
        # Each word keeps the spaces after it, so a "•  " prefix or an indent
        # survives the rebuild exactly as it was written.
        tokens = [(m.group(1), m.group(2)) for m in re.finditer(r"([^ ]+)( *)", para)]
        words = [w for w, _ in tokens]
        n = len(words)
        if n <= 1 or width(para, size, metrics) <= max_w:
            out.append(para.rstrip())
            continue

        def line(i: int, j: int) -> str:
            body = "".join(w + sep for w, sep in tokens[i:j]).rstrip(" ")
            return (lead + body) if i == 0 else body

        widths: dict[tuple[int, int], float] = {}

        def w_of(i: int, j: int) -> float:
            key = (i, j)
            if key not in widths:
                widths[key] = width(line(i, j), size, metrics)
            return widths[key]

        best: list[tuple[float, list[str]] | None] = [None] * (n + 1)
        best[n] = (0.0, [])
        for i in range(n - 1, -1, -1):
            for j in range(i + 1, n + 1):
                lw = w_of(i, j)
                if lw > max_w and j > i + 1:
                    break
                if best[j] is None:
                    continue
                slack = max(0.0, (max_w - lw) / max_w)
                last = j == n
                cost = 0.0 if last else 100 * slack * slack  # balanced lines
                if not last:
                    cost += cost_break(words[j - 1], words[j], first=j == 1)
                if last and j - i == 1 and n > 2:
                    cost += 300.0  # one orphan word on the last line
                cost += 30.0  # each extra line costs: stay compact
                total = cost + best[j][0]
                if best[i] is None or total < best[i][0]:
                    best[i] = (total, [line(i, j), *best[j][1]])
                if lw > max_w:
                    break
        out.extend(best[0][1] if best[0] else [para])
    return out


def break_lines(
    text: str,
    size: float,
    box_width_pt: float,
    *,
    family: str | None = None,
    bold: bool = False,
) -> str:
    """*text* with its line breaks chosen (``\\v`` between lines), ready to write.

    A no-break space the face has no glyph for is written as a plain space:
    the break it protected is now ours to choose, and the cost model already
    keeps a number with its unit and a « : » off the start of a line.
    """
    metrics = face(family, bold)
    lines = wrap(text, size, box_width_pt, metrics)
    joined = "\v".join(lines)
    for ch in _NBSP:
        if ch in joined and not has_glyph(metrics, ch):
            joined = joined.replace(ch, " ")
    return joined
