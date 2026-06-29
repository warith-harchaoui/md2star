"""Unit tests for :mod:`md2star.postprocess`.

The post-processor reopens a Pandoc-produced ``.docx`` zip, locates
``word/styles.xml``, and injects the ``MyTable`` and ``MyTableSmall``
custom table styles that Pandoc strips when it rewrites its style catalogue.

These tests build a minimal valid DOCX from scratch (zip with the two XML
files Pandoc would have written) so we never need pandoc itself on PATH.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile

from md2star.postprocess import inject_table_styles, strip_table_normal_for_pdf

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


# ──────────────────────────────────────────────────────────────────


def test_injects_both_styles_on_empty_styles_xml(tmp_path) -> None:
    """Empty styles.xml → MyTable + MyTableSmall added; function returns True."""
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)

    changed = inject_table_styles(str(docx))
    assert changed is True

    root = _styles_root(docx)
    assert _has_style(root, "MyTable")
    assert _has_style(root, "MyTableSmall")


def test_idempotent_second_run_is_noop(tmp_path) -> None:
    """A second call must not duplicate the injected styles and must return False."""
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)

    # First run: adds both.
    assert inject_table_styles(str(docx)) is True

    # Second run: nothing to do.
    assert inject_table_styles(str(docx)) is False

    root = _styles_root(docx)
    # Exactly one of each, no duplicates.
    mytable_count = sum(
        1
        for s in root.findall(f"{{{_W_NS}}}style")
        if s.get(f"{{{_W_NS}}}styleId") == "MyTable"
    )
    small_count = sum(
        1
        for s in root.findall(f"{{{_W_NS}}}style")
        if s.get(f"{{{_W_NS}}}styleId") == "MyTableSmall"
    )
    assert mytable_count == 1
    assert small_count == 1


def test_borders_use_expected_color(tmp_path) -> None:
    """The injected ``<w:tblBorders>`` uses the documented #9E9E9E grey."""
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)
    inject_table_styles(str(docx))

    with zipfile.ZipFile(docx) as z:
        styles = z.read("word/styles.xml").decode("utf-8")

    # Just spot-check that the color attribute lands on at least one border.
    # We do this on raw text rather than ElementTree to avoid namespace gymnastics.
    assert 'w:color="9E9E9E"' in styles


def test_other_zip_entries_preserved(tmp_path) -> None:
    """The rewrite must preserve every other file in the zip byte-for-byte."""
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)
    original_document = _MINIMAL_DOCUMENT_XML

    inject_table_styles(str(docx))

    with zipfile.ZipFile(docx) as z:
        # ``word/document.xml`` was untouched — must round-trip byte-identical.
        assert z.read("word/document.xml") == original_document


def test_partial_existing_styles_only_adds_missing(tmp_path) -> None:
    """If MyTable already exists, only MyTableSmall is added (and vice-versa)."""
    docx = tmp_path / "blank.docx"
    # Pre-seed styles.xml with just MyTable already in place.
    pre_seeded = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<w:styles xmlns:w="{_W_NS}">'
        '<w:docDefaults><w:rPrDefault><w:rPr/></w:rPrDefault></w:docDefaults>'
        f'<w:style w:type="table" w:customStyle="1" w:styleId="MyTable">'
        '<w:name w:val="MyTable"/></w:style>'
        '</w:styles>'
    ).encode("utf-8")
    with zipfile.ZipFile(docx, "w", zipfile.ZIP_DEFLATED) as zout:
        zout.writestr("word/styles.xml", pre_seeded)
        zout.writestr("word/document.xml", _MINIMAL_DOCUMENT_XML)

    assert inject_table_styles(str(docx)) is True

    root = _styles_root(docx)
    mytable_count = sum(
        1
        for s in root.findall(f"{{{_W_NS}}}style")
        if s.get(f"{{{_W_NS}}}styleId") == "MyTable"
    )
    # Should still be exactly one (no duplicate).
    assert mytable_count == 1
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


def test_strip_table_normal_removes_style_and_refs(tmp_path) -> None:
    """The function drops the style block AND every body-level ``<w:tblStyle>`` ref."""
    docx = tmp_path / "intermediate.docx"
    _build_docx_with_table_normal(docx)

    assert strip_table_normal_for_pdf(str(docx)) is True

    with zipfile.ZipFile(docx) as z:
        styles = z.read("word/styles.xml").decode("utf-8")
        document = z.read("word/document.xml").decode("utf-8")

    # Style definition is gone.
    assert 'w:styleId="TableNormal0"' not in styles
    # The reference inside the body is gone too.
    assert 'TableNormal0' not in document
    # The table cell text survived; we only excised the style hook.
    assert "<w:t>cell</w:t>" in document


def test_strip_table_normal_idempotent_when_absent(tmp_path) -> None:
    """A DOCX that never had TableNormal0 returns False and is byte-identical after."""
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)

    with open(docx, "rb") as f:
        before = f.read()

    assert strip_table_normal_for_pdf(str(docx)) is False

    with open(docx, "rb") as f:
        after = f.read()
    assert before == after
