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


def test_inject_adds_styles_with_border_colour_and_preserves_zip(tmp_path) -> None:
    """A fresh inject lands both styles, the grey border, and touches nothing else.

    Bundles four assertions that describe one realistic first-injection run:
    the return flag, both style ids, the documented ``#9E9E9E`` border
    colour, and byte-for-byte preservation of the sibling document part.
    """
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)

    # A first injection into an empty catalogue reports that it changed the file.
    changed = inject_table_styles(str(docx))
    assert changed is True

    # Both custom table styles are now declared.
    root = _styles_root(docx)
    assert _has_style(root, "MyTable")
    assert _has_style(root, "MyTableSmall")

    # The injected borders use the documented grey; spot-check on raw text to
    # avoid namespace gymnastics around the nested <w:tblBorders> element.
    with zipfile.ZipFile(docx) as z:
        styles = z.read("word/styles.xml").decode("utf-8")
        document = z.read("word/document.xml")
    assert 'w:color="9E9E9E"' in styles

    # The rewrite only rewrote styles.xml — document.xml round-trips identical.
    assert document == _MINIMAL_DOCUMENT_XML


def test_inject_is_idempotent_and_only_adds_missing(tmp_path) -> None:
    """Re-running never duplicates, and a partial catalogue only gains the gap.

    Two regression facets in one scenario: a repeated run on a fully-injected
    file is a no-op (returns False, no duplicate styles), and a catalogue that
    already carries ``MyTable`` gains only the still-missing ``MyTableSmall``.
    """
    # --- Idempotency: second run over a fully-injected file is a no-op. ---
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)
    assert inject_table_styles(str(docx)) is True   # first run adds both
    assert inject_table_styles(str(docx)) is False  # second run: nothing to do

    root = _styles_root(docx)
    # Exactly one of each — the second run added no duplicates.
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


def test_strip_table_normal_removes_style_and_refs(tmp_path) -> None:
    """The function drops the style block AND every body-level ``<w:tblStyle>`` ref."""
    docx = tmp_path / "intermediate.docx"
    _build_docx_with_table_normal(docx)

    # The offending style + refs are present, so the strip reports a change.
    assert strip_table_normal_for_pdf(str(docx)) is True

    with zipfile.ZipFile(docx) as z:
        styles = z.read("word/styles.xml").decode("utf-8")
        document = z.read("word/document.xml").decode("utf-8")

    # Style definition is gone from the catalogue.
    assert 'w:styleId="TableNormal0"' not in styles
    # The reference inside the body is gone too.
    assert 'TableNormal0' not in document
    # The table cell text survived; we only excised the style hook.
    assert "<w:t>cell</w:t>" in document


def test_strip_table_normal_idempotent_when_absent(tmp_path) -> None:
    """A DOCX that never had TableNormal0 returns False and is byte-identical after."""
    docx = tmp_path / "blank.docx"
    _build_minimal_docx(docx)

    # Snapshot the whole archive before the no-op strip.
    before = docx.read_bytes()

    # Nothing to remove → the function reports no change.
    assert strip_table_normal_for_pdf(str(docx)) is False

    # And it must not have rewritten a single byte.
    assert docx.read_bytes() == before
