"""postprocess.py — Re-inject Pandoc-stripped styles into the output DOCX.

Pandoc's DOCX writer reads the reference template's ``word/styles.xml`` but
rewrites it from its own catalogue on output. Paragraph and character styles
defined in the reference *that Pandoc happens to use* survive; arbitrary
custom-styled **table** styles do not — Pandoc drops them, leaving the
``<w:tblStyle w:val="X"/>`` references in the body pointing at nothing.

This module reopens the produced ``.docx`` zip, locates ``word/styles.xml``,
and inserts the ``MyTable`` and ``MyTableSmall`` table styles (thin gray
``#9E9E9E`` borders; the small variant also forces an 8 pt font + tighter
cell margins). It is idempotent: existing definitions are left untouched.

The XML is parsed with :mod:`xml.etree.ElementTree` rather than mutated as
a string, so trailing whitespace, attribute ordering, or namespace prefix
differences cannot break the rewrite.

Invoked by the ``md2docx`` CLI immediately after Pandoc finishes.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import os
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile

from .logging import get_logger

# Module logger — child of the root "md2star" logger (configured by the CLI).
logger = get_logger(__name__)

# WordprocessingML namespace. We register it as the default prefix ``w`` so
# the serialized output matches what every other Office tooling produces.
_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", _W_NS)


_BORDERS = (
    f'<w:tblBorders xmlns:w="{_W_NS}">'
    '<w:top w:val="single" w:sz="4" w:space="0" w:color="9E9E9E"/>'
    '<w:left w:val="single" w:sz="4" w:space="0" w:color="9E9E9E"/>'
    '<w:bottom w:val="single" w:sz="4" w:space="0" w:color="9E9E9E"/>'
    '<w:right w:val="single" w:sz="4" w:space="0" w:color="9E9E9E"/>'
    '<w:insideH w:val="single" w:sz="4" w:space="0" w:color="9E9E9E"/>'
    '<w:insideV w:val="single" w:sz="4" w:space="0" w:color="9E9E9E"/>'
    '</w:tblBorders>'
)

_MYTABLE = (
    f'<w:style xmlns:w="{_W_NS}" w:type="table" w:customStyle="1" w:styleId="MyTable">'
    '<w:name w:val="MyTable"/>'
    '<w:tblPr>'
    f'{_BORDERS}'
    '<w:tblCellMar>'
    '<w:top w:w="60" w:type="dxa"/>'
    '<w:left w:w="108" w:type="dxa"/>'
    '<w:bottom w:w="60" w:type="dxa"/>'
    '<w:right w:w="108" w:type="dxa"/>'
    '</w:tblCellMar>'
    '</w:tblPr>'
    '</w:style>'
)

_MYTABLE_SMALL = (
    f'<w:style xmlns:w="{_W_NS}" w:type="table" w:customStyle="1" w:styleId="MyTableSmall">'
    '<w:name w:val="MyTableSmall"/>'
    '<w:pPr><w:rPr><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr></w:pPr>'
    '<w:rPr><w:sz w:val="16"/><w:szCs w:val="16"/></w:rPr>'
    '<w:tblPr>'
    f'{_BORDERS}'
    '<w:tblCellMar>'
    '<w:top w:w="30" w:type="dxa"/>'
    '<w:left w:w="72" w:type="dxa"/>'
    '<w:bottom w:w="30" w:type="dxa"/>'
    '<w:right w:w="72" w:type="dxa"/>'
    '</w:tblCellMar>'
    '</w:tblPr>'
    '</w:style>'
)


def _has_style(root: ET.Element, style_id: str) -> bool:
    """Return True if ``root`` already declares a ``<w:style w:styleId="...">``."""
    for style in root.findall(f"{{{_W_NS}}}style"):
        if style.get(f"{{{_W_NS}}}styleId") == style_id:
            return True
    return False


def inject_table_styles(docx_path: str) -> bool:
    """Inject MyTable + MyTableSmall into *docx_path*'s ``word/styles.xml``.

    Returns True if any style was added, False if both were already present
    (or if the styles.xml could not be parsed — defensive no-op).
    """
    with zipfile.ZipFile(docx_path, "r") as zin:
        styles_bytes = zin.read("word/styles.xml")

    try:
        root = ET.fromstring(styles_bytes)
    except ET.ParseError as exc:
        # Defensive: a malformed styles.xml means we skip injection rather
        # than corrupt the .docx — warn and leave the document as pandoc built it.
        logger.warning(
            f"md2star warning: word/styles.xml parse failed ({exc}); skipping inject"
        )
        return False

    changed = False
    if not _has_style(root, "MyTable"):
        root.append(ET.fromstring(_MYTABLE))
        changed = True
    if not _has_style(root, "MyTableSmall"):
        root.append(ET.fromstring(_MYTABLE_SMALL))
        changed = True

    if not changed:
        return False

    new_styles = ET.tostring(root, encoding="utf-8", xml_declaration=True)

    # A .docx is a zip and zips can't be edited in place, so rebuild it into a
    # sibling temp file, swapping only word/styles.xml, then atomically move it
    # over the original — a crash mid-write can't corrupt the user's document.
    tmp_path = docx_path + ".tmp"
    with zipfile.ZipFile(docx_path, "r") as zin, zipfile.ZipFile(
        tmp_path, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            # Copy every member verbatim except the styles part we mutated.
            data = zin.read(item.filename)
            if item.filename == "word/styles.xml":
                data = new_styles
            zout.writestr(item, data)

    shutil.move(tmp_path, docx_path)
    return True


# ─────────────────────────────────────────────────────────────────────
# PDF-path workaround — strip the bundled template's ``TableNormal0``
# style so headless LibreOffice renders tables correctly.
# ─────────────────────────────────────────────────────────────────────
#
# Word renders tables built on the bundled template's ``TableNormal0``
# custom-style correctly. LibreOffice headless (`soffice --convert-to
# pdf`) does not — cell content leaks out of the table as a vertical
# paragraph dump. Documented in CHANGELOG v1.1.1 as a known issue.
#
# The DOCX path is fine (Word users get the styled tables). Only the
# *intermediate* DOCX produced as a stepping stone toward PDF needs
# fixing. We rewrite that DOCX to:
#
# 1. Remove the ``TableNormal0`` style definition from ``styles.xml``.
# 2. Strip ``<w:tblStyle w:val="TableNormal0"/>`` references from
#    every ``word/*.xml`` (document.xml, header*.xml, footer*.xml) so
#    tables fall back to the renderer's default styling.
#
# Both ends of the surgery are zip-level; no Pandoc rerun, no template
# rebuild. The function is idempotent — a docx without the style /
# references is left untouched.


def _strip_table_normal_xml(xml_bytes: bytes) -> tuple[bytes, bool]:
    """Strip ``TableNormal0`` from a styles.xml-compatible XML payload.

    Removes the ``<w:style w:styleId="TableNormal0">`` block from the
    root if present. Returns ``(new_bytes, changed)``.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return xml_bytes, False
    # ElementTree needs the fully-qualified {namespace}tag form to match WordML.
    style_tag = f"{{{_W_NS}}}style"
    style_id_attr = f"{{{_W_NS}}}styleId"
    # Find the one <w:style> whose styleId is TableNormal0 (if any).
    victim = None
    for style in root.findall(style_tag):
        if style.get(style_id_attr) == "TableNormal0":
            victim = style
            break
    # Absent already → report "unchanged" so the caller can no-op (idempotent).
    if victim is None:
        return xml_bytes, False
    root.remove(victim)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True), True


def _strip_table_normal_refs(xml_bytes: bytes) -> tuple[bytes, bool]:
    """Strip ``<w:tblStyle w:val="TableNormal0"/>`` refs from a body XML payload.

    Operates as a string replacement because ``tblStyle`` always
    appears as a self-closing element with a single ``w:val``
    attribute, and parsing the entire document.xml (~MBs) just to
    drop one element type would be wasteful. Handles both
    ``w:val="TableNormal0"`` and ``w:val='TableNormal0'`` quoting.
    """
    needle_double = b'<w:tblStyle w:val="TableNormal0"/>'
    needle_single = b"<w:tblStyle w:val='TableNormal0'/>"
    if needle_double not in xml_bytes and needle_single not in xml_bytes:
        return xml_bytes, False
    out = xml_bytes.replace(needle_double, b"").replace(needle_single, b"")
    return out, True


def strip_table_normal_for_pdf(docx_path: str) -> bool:
    """Neutralize the bundled template's ``TableNormal0`` in *docx_path*.

    Word renders the style fine; LibreOffice headless does not. We
    call this on the *intermediate* DOCX produced inside the
    ``md2pdf`` pipeline so the soffice render is correct. The user's
    DOCX output (when they call ``md2docx``) is untouched.

    Returns True if any mutation happened, False otherwise.
    """
    with zipfile.ZipFile(docx_path, "r") as zin:
        members = {item.filename: zin.read(item.filename) for item in zin.infolist()}

    changed_any = False
    # 1. Drop the style block from styles.xml.
    if "word/styles.xml" in members:
        new_bytes, changed = _strip_table_normal_xml(members["word/styles.xml"])
        if changed:
            members["word/styles.xml"] = new_bytes
            changed_any = True

    # 2. Drop the tblStyle reference from every body part. Headers /
    #    footers can reference table styles too if the template uses
    #    them, so we walk every ``word/`` XML file rather than just
    #    document.xml.
    for name in list(members):
        if not name.startswith("word/") or not name.endswith(".xml"):
            continue
        if name == "word/styles.xml":
            continue
        new_bytes, changed = _strip_table_normal_refs(members[name])
        if changed:
            members[name] = new_bytes
            changed_any = True

    if not changed_any:
        return False

    tmp_path = docx_path + ".tmp"
    with zipfile.ZipFile(docx_path, "r") as zin, zipfile.ZipFile(
        tmp_path, "w", zipfile.ZIP_DEFLATED
    ) as zout:
        for item in zin.infolist():
            data = members.get(item.filename, zin.read(item.filename))
            zout.writestr(item, data)

    shutil.move(tmp_path, docx_path)
    return True


if __name__ == "__main__":
    # Standalone debug entry (`python -m md2star.postprocess <file.docx>`):
    # configure logging ourselves since there's no CLI wrapper to do it.
    from .logging import configure as _configure_logging
    _configure_logging()

    if len(sys.argv) != 2:
        logger.error("Usage: python -m md2star.postprocess <output.docx>")
        sys.exit(1)
    path = sys.argv[1]
    if not os.path.exists(path):
        logger.warning(f"md2star warning: {path} not found")
        sys.exit(0)
    inject_table_styles(path)
