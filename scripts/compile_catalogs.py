#!/usr/bin/env python3
"""Compile md2star's ``.po`` catalogues into the ``.mo`` files gettext reads.

GNU gettext's own ``msgfmt`` would do this, and requiring it would mean a
translated interface could only be built on a machine where somebody had
installed the gettext tools — on macOS, that is a Homebrew package. The ``.mo``
format is a header, two offset tables and a blob of strings, so md2star writes
it rather than depending on that. Same reasoning as everywhere else here: the
thing is small, the dependency is not.

Usage
-----
::

    python scripts/compile_catalogs.py            # compile every .po in place
    python scripts/compile_catalogs.py --check    # fail if any .mo is stale

``--check`` is what CI wants: it recompiles in memory and compares, so a
translation edited without recompiling cannot reach a release looking live.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import argparse
import array
import re
import struct
import sys
from pathlib import Path

#: ``.mo`` magic, little-endian. The byte order is the file's own declaration,
#: so writing little-endian everywhere is portable, not host-dependent.
_MAGIC = 0x950412DE

#: One entry line, with the string in C-escaped quotes. ``msgstr[0]`` and
#: ``msgstr[1]`` are the plural forms, which French needs and English mostly
#: does not — hence the optional index.
_ENTRY_RE = re.compile(r'^(msgid|msgid_plural|msgstr)(?:\[(\d+)\])?\s+"(.*)"\s*$')
#: A continuation line: a bare quoted string under the entry it extends.
_CONT_RE = re.compile(r'^\s*"(.*)"\s*$')


def _unescape(text: str) -> str:
    """Turn a ``.po``'s C escapes back into the characters they stand for."""
    return text.replace(r"\n", "\n").replace(r"\t", "\t").replace(r"\"", '"').replace(r"\\", "\\")


def parse_po(path: Path) -> dict[str, str]:
    """Read a ``.po`` into the ``{key: value}`` a ``.mo`` stores.

    Plural entries are kept, because they are the reason a French catalogue
    exists at all: gettext stores them by NUL-joining the two ``msgid`` forms
    into one key and the ``msgstr[n]`` forms into one value, which is exactly
    what :func:`build_mo` then writes. Contexts (``msgctxt``) are not handled —
    md2star has none, and a parser that half-read them would be worse than one
    that says so.

    An entry with an empty translation is dropped, which is what makes an
    unfinished catalogue fall back to its English source rather than serve
    emptiness.
    """
    entries: dict[str, str] = {}
    singular: str | None = None
    plural: str | None = None
    translations: dict[int, str] = {}
    current: tuple[str, int] | None = None
    buffer: list[str] = []

    def commit() -> None:
        """Close the entry being read and file it."""
        nonlocal singular, plural, translations
        if singular is None:
            return
        if plural is None:
            value = translations.get(0, "")
            if value or singular == "":
                entries[singular] = value
        else:
            forms = [translations.get(i, "") for i in range(max(translations) + 1)]
            if any(forms):
                entries[f"{singular}\x00{plural}"] = "\x00".join(forms)
        singular, plural, translations = None, None, {}

    def flush() -> None:
        """Attach the lines gathered so far to the field they belong to."""
        nonlocal singular, plural
        if current is None:
            return
        field, index = current
        text = "".join(buffer)
        if field == "msgid":
            commit()
            singular = text
        elif field == "msgid_plural":
            plural = text
        else:
            translations[index] = text

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        match = _ENTRY_RE.match(line)
        if match:
            flush()
            current = (match.group(1), int(match.group(2) or 0))
            buffer = [_unescape(match.group(3))]
            continue
        cont = _CONT_RE.match(line)
        if cont and current is not None:
            buffer.append(_unescape(cont.group(1)))
    flush()
    commit()
    return entries


def build_mo(entries: dict[str, str]) -> bytes:
    """Serialise ``{msgid: msgstr}`` into the binary gettext reads.

    Layout, in order: a 28-byte header, the originals' (length, offset) table,
    the translations' table, then the two blobs. Entries must be sorted by
    ``msgid`` — gettext binary-searches them. A plural entry arrives here
    already NUL-joined on both sides, which is how the format carries it.
    """
    items = sorted(entries.items())
    ids = b"\x00".join(key.encode("utf-8") for key, _ in items) + b"\x00"
    strs = b"\x00".join(value.encode("utf-8") for _, value in items) + b"\x00"
    count = len(items)
    # Header is 7 unsigned ints; the two tables are 2 ints per entry each.
    key_table = 7 * 4
    value_table = key_table + count * 8
    ids_start = value_table + count * 8
    strs_start = ids_start + len(ids)

    offsets: list[int] = []
    position = 0
    for key, _value in items:
        encoded = len(key.encode("utf-8"))
        offsets.append(encoded)
        offsets.append(ids_start + position)
        position += encoded + 1
    position = 0
    for _key, value in items:
        encoded = len(value.encode("utf-8"))
        offsets.append(encoded)
        offsets.append(strs_start + position)
        position += encoded + 1

    header = struct.pack(
        "<7I",
        _MAGIC,
        0,  # format revision
        count,
        key_table,
        value_table,
        0,  # hash table size: zero is legal and gettext falls back to search
        strs_start + len(strs),
    )
    return header + array.array("i", offsets).tobytes() + ids + strs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="compile_catalogs")
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if any .mo differs from its .po",
    )
    parser.add_argument(
        "--root",
        default="md2star/data/locales",
        help="directory holding <lang>/LC_MESSAGES/*.po",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    sources = sorted(root.glob("*/LC_MESSAGES/*.po"))
    if not sources:
        print(f"compile_catalogs: no .po under {root}", file=sys.stderr)
        return 1
    stale = 0
    for po in sources:
        mo = po.with_suffix(".mo")
        built = build_mo(parse_po(po))
        if args.check:
            if not mo.is_file() or mo.read_bytes() != built:
                print(f"stale: {mo}", file=sys.stderr)
                stale += 1
            continue
        mo.write_bytes(built)
        print(f"wrote {mo} ({len(parse_po(po))} entries)")
    if args.check:
        if stale:
            print(
                f"compile_catalogs: {stale} catalogue(s) out of date; "
                "run `python scripts/compile_catalogs.py`",
                file=sys.stderr,
            )
            return 1
        print(f"compile_catalogs: {len(sources)} catalogue(s) up to date ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
