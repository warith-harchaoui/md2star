"""Unit tests for :mod:`md2star.postprocess`.

The post-processor reopens a Pandoc-produced ``.docx`` zip, locates
``word/styles.xml``, and injects the ``MyTable`` and ``MyTableSmall``
custom table styles that Pandoc strips when it rewrites its style
catalogue. A companion pass (:func:`strip_table_normal_for_pdf`) removes
the bundled template's ``TableNormal0`` style + its body references so
soffice can render the intermediate DOCX to PDF.

These tests build minimal valid DOCX zips from scratch (only the two XML
files Pandoc would have written) so we never need pandoc itself on PATH.
The seven original cases collapse into four functional scenarios:

* injection: both styles land, the return flag is truthy, the border
  colour is correct, and unrelated zip entries survive byte-for-byte;
* idempotency + partial re-injection (regression — no duplicates);
* ``strip_table_normal_for_pdf`` excising the style and its refs;
* ``strip_table_normal_for_pdf`` as a no-op byte-identical passthrough.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

from md2star.postprocess import (
    center_standalone_images,
    inject_table_styles,
    strip_table_normal_for_pdf,
)

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


_EMPTY_STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:styles xmlns:w="{_W_NS}">'
    '<w:docDefaults><w:rPrDefault><w:rPr/></w:rPrDefault></w:docDefaults>'
    '</w:styles>'
).encode("utf-8")


_MINIMAL_DOCUMENT_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    f'<w:document xmlns:w="{_W_NS}"><w:body><w:p/></w:body></w:document>'
).encode("utf-8")


def _build_minimal_docx(path) -> None:
    """Write a tiny but valid OOXML zip to *path*.

    The zip contains only the two files our postprocessor cares about
    (``word/styles.xml`` + ``word/document.xml``). It is enough for
    :func:`inject_table_styles` to round-trip without errors.
    """
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("word/styles.xml", _EMPTY_STYLES_XML)
        zout.writestr("word/document.xml", _MINIMAL_DOCUMENT_XML)


def _styles_root(path) -> ET.Element:
    """Return the parsed ``word/styles.xml`` from *path*."""
    with zipfile.ZipFile(path) as z:
        return ET.fromstring(z.read("word/styles.xml"))


def _has_style(root: ET.Element, style_id: str) -> bool:
    """True if *root* declares a ``<w:style w:styleId="...">`` with the given id."""
    for style in root.findall(f"{{{_W_NS}}}style"):
        if style.get(f"{{{_W_NS}}}styleId") == style_id:
            return True
    return False


def _style_count(root: ET.Element, style_id: str) -> int:
    """Return how many ``<w:style>`` blocks in *root* carry *style_id*."""
    return sum(
        1
        for s in root.findall(f"{{{_W_NS}}}style")
        if s.get(f"{{{_W_NS}}}styleId") == style_id
    )


# ──────────────────────────────────────────────────────────────────
# inject_table_styles — the happy path plus its structural guarantees.
# ──────────────────────────────────────────────────────────────────


def test_inject_adds_styles_then_is_idempotent_and_gap_filling(tmp_path) -> None:
    """A fresh inject lands both styles + grey border; re-runs never duplicate.

    One end-to-end story: the first injection reports a change, declares both
    styles, uses the documented ``#9E9E9E`` border, and leaves document.xml
    byte-identical; a second run is a no-op (no duplicates); and a catalogue
    already carrying ``MyTable`` gains only the still-missing ``MyTableSmall``.
    """
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)

    # First injection into an empty catalogue reports it changed the file.
    assert inject_table_styles(str(docx)) is True

    root = _styles_root(docx)
    assert _has_style(root, "MyTable") and _has_style(root, "MyTableSmall")

    # Grey border present; document.xml untouched (only styles.xml rewritten).
    with zipfile.ZipFile(docx) as z:
        styles = z.read("word/styles.xml").decode("utf-8")
        document = z.read("word/document.xml")
    assert 'w:color="9E9E9E"' in styles
    assert document == _MINIMAL_DOCUMENT_XML

    # Idempotency: a second run is a no-op with no duplicate styles.
    assert inject_table_styles(str(docx)) is False
    root = _styles_root(docx)
    assert _style_count(root, "MyTable") == 1
    assert _style_count(root, "MyTableSmall") == 1

    # --- Partial catalogue: only the missing style is appended. ---
    partial = tmp_path / "partial.docx"
    pre_seeded = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{_W_NS}">'
        '<w:docDefaults><w:rPrDefault><w:rPr/></w:rPrDefault></w:docDefaults>'
        '<w:style w:type="table" w:customStyle="1" w:styleId="MyTable">'
        '<w:name w:val="MyTable"/></w:style>'
        '</w:styles>'
    ).encode("utf-8")
    with zipfile.ZipFile(partial, "w", zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("word/styles.xml", pre_seeded)
        zout.writestr("word/document.xml", _MINIMAL_DOCUMENT_XML)

    # A file that is missing exactly one style still reports a change.
    assert inject_table_styles(str(partial)) is True

    root = _styles_root(partial)
    # MyTable stays single (not re-added) and MyTableSmall is now present.
    assert _style_count(root, "MyTable") == 1
    assert _has_style(root, "MyTableSmall")


# ──────────────────────────────────────────────────────────────────
# strip_table_normal_for_pdf — soffice workaround for the bundled
# template's TableNormal0 custom style.
# ──────────────────────────────────────────────────────────────────


def _build_docx_with_table_normal(path) -> None:
    """Write a tiny DOCX zip that mimics the bundled template + a table body.

    The DOCX has:
    - ``word/styles.xml`` containing the offending ``TableNormal0`` block.
    - ``word/document.xml`` containing a table whose ``tblPr`` references
      ``TableNormal0`` (the shape Pandoc emits when fed the bundled template).
    """
    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{_W_NS}">'
        '<w:docDefaults><w:rPrDefault><w:rPr/></w:rPrDefault></w:docDefaults>'
        '<w:style w:type="table" w:customStyle="1" w:styleId="TableNormal0">'
        '<w:name w:val="TableNormal"/>'
        '<w:tblPr><w:tblCellMar>'
        '<w:top w:w="100" w:type="dxa"/><w:left w:w="100" w:type="dxa"/>'
        '<w:bottom w:w="100" w:type="dxa"/><w:right w:w="100" w:type="dxa"/>'
        '</w:tblCellMar></w:tblPr></w:style>'
        '</w:styles>'
    ).encode("utf-8")
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W_NS}"><w:body>'
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableNormal0"/></w:tblPr>'
        '<w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr>'
        '</w:tbl>'
        '</w:body></w:document>'
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("word/styles.xml", styles)
        zout.writestr("word/document.xml", document)


def test_strip_table_normal_removes_refs_and_is_a_noop_when_absent(tmp_path) -> None:
    """The strip drops the style block + body refs, and is a byte-noop when absent.

    Two facets of one function: on a DOCX carrying ``TableNormal0`` it reports a
    change, removes the style definition and every body ``<w:tblStyle>`` ref
    (keeping the cell text); on a DOCX that never had it, it returns False and
    rewrites not a single byte.
    """
    # Present: the strip removes the style + refs but keeps content.
    docx = tmp_path / "intermediate.docx"
    _build_docx_with_table_normal(docx)
    assert strip_table_normal_for_pdf(str(docx)) is True
    with zipfile.ZipFile(docx) as z:
        styles = z.read("word/styles.xml").decode("utf-8")
        document = z.read("word/document.xml").decode("utf-8")
    assert 'w:styleId="TableNormal0"' not in styles
    assert "TableNormal0" not in document
    assert "<w:t>cell</w:t>" in document  # cell text survived

    # Absent: nothing to remove → no change, byte-identical archive.
    blank = tmp_path / "blank.docx"
    _build_minimal_docx(blank)
    before = blank.read_bytes()
    assert strip_table_normal_for_pdf(str(blank)) is False
    assert blank.read_bytes() == before


# ──────────────────────────────────────────────────────────────────
# center_standalone_images — centre bare images, only outside tables.
# ──────────────────────────────────────────────────────────────────


def _build_docx_with_images(path) -> None:
    """A DOCX with four paragraphs: text-only, a bare image, an image beside
    text, and an image inside a table cell."""
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:document xmlns:w="{_W_NS}"><w:body>'
        '<w:p><w:r><w:t>text only</w:t></w:r></w:p>'
        '<w:p><w:r><w:drawing/></w:r></w:p>'                       # standalone image
        '<w:p><w:r><w:t>caption </w:t></w:r><w:r><w:drawing/></w:r></w:p>'  # image + text
        '<w:tbl><w:tr><w:tc>'
        '<w:p><w:r><w:drawing/></w:r></w:p>'                       # image in a table cell
        '</w:tc></w:tr></w:tbl>'
        '</w:body></w:document>'
    ).encode("utf-8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("word/document.xml", document)


def test_center_standalone_images_only_bare_images_outside_tables(tmp_path) -> None:
    """Only the bare, non-table image paragraph is centred; the pass is idempotent.

    The text-only paragraph has no image, the image-beside-text paragraph carries
    real text, and the table-cell image is *hors tableau*-excluded — so exactly
    one ``<w:jc w:val="center"/>`` is added, and a second run is a no-op.
    """
    docx = tmp_path / "imgs.docx"
    _build_docx_with_images(docx)

    assert center_standalone_images(str(docx)) is True
    with zipfile.ZipFile(docx) as z:
        document = z.read("word/document.xml").decode("utf-8")
    # Exactly one centred paragraph — the standalone image.
    assert document.count('<w:jc w:val="center"') == 1
    # The centred one sits before the table (it is the bare image paragraph).
    assert document.index('<w:jc w:val="center"') < document.index("<w:tbl")

    # Idempotency: a second run changes nothing.
    assert center_standalone_images(str(docx)) is False
