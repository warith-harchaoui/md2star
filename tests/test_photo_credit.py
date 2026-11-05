"""Photo credits: an image's Markdown title printed small over the picture.

``![](photo.jpg "Courtesy of https://...")`` — the title is a credit, set in a
small plate inside the placed picture's frame (bottom right, or top right when
a title band holds the bottom), never shortened, never the picture's alt text,
and exempt from the audit's type floors the way a footer is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")

from pptx.util import Inches  # noqa: E402

from md2star import pptx_assemble as pa  # noqa: E402
from md2star import pptx_audit as au  # noqa: E402
from md2star import pptx_layout as pl  # noqa: E402

URL = "Courtesy of https://www.nga.gov/artworks/195605-gallery-drouot"
SHOWN = "Courtesy of nga.gov"
LINK = "https://www.nga.gov/artworks/195605-gallery-drouot"


@pytest.fixture
def images(tmp_path: Path) -> Path:
    from PIL import Image

    Image.new("RGB", (1600, 1000), (200, 200, 190)).save(tmp_path / "pic.png")
    return tmp_path


@pytest.fixture
def default_template(tmp_path: Path) -> Path:
    path = tmp_path / "default.pptx"
    pptx.Presentation().save(str(path))
    return path


@pytest.fixture
def photo_template(tmp_path: Path) -> Path:
    """A "Photo" page: a picture placeholder over the whole slide, a band at its foot."""
    prs = pptx.Presentation()
    layout = prs.slide_layouts.get_by_name("Picture with Caption")
    layout.name = "Photo"
    for ph in layout.placeholders:
        kind = str(ph.placeholder_format.type)
        if "PICTURE" in kind:
            ph.left, ph.top, ph.width, ph.height = 0, 0, prs.slide_width, prs.slide_height
        elif "TITLE" in kind:
            ph.left, ph.top = Inches(0.5), Inches(6.2)
            ph.width, ph.height = Inches(9), Inches(0.8)
    from pptx.enum.shapes import MSO_SHAPE

    scratch = prs.slides.add_slide(prs.slide_layouts[6])
    band = scratch.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, Inches(6), prs.slide_width, Inches(1.5))
    band.name = "band"
    layout.shapes._spTree.insert(2, band._element)
    rid = prs.slides._sldIdLst[-1].rId
    prs.part.drop_rel(rid)
    prs.slides._sldIdLst.remove(prs.slides._sldIdLst[-1])
    path = tmp_path / "photo.pptx"
    prs.save(str(path))
    return path


def _credits(slide) -> list:
    return [sh for sh in slide.shapes if sh.name == pa.CREDIT_NAME]


def _pictures(slide) -> list:
    return [sh for sh in slide.shapes if sh.shape_type == 13]


def _box(sh) -> tuple[int, int, int, int]:
    return (sh.left, sh.top, sh.width, sh.height)


def _inside(inner, outer, slack: int = 2) -> bool:
    return (
        inner[0] >= outer[0] - slack
        and inner[1] >= outer[1] - slack
        and inner[0] + inner[2] <= outer[0] + outer[2] + slack
        and inner[1] + inner[3] <= outer[1] + outer[3] + slack
    )


def _sizes(shape) -> set[float]:
    return {r.font.size.pt for p in shape.text_frame.paragraphs for r in p.runs}


class TestParsing:
    @pytest.mark.parametrize(
        ("body", "credit"),
        [
            (f'![](a.jpg "{URL}")', URL),
            ("![](a.jpg 'single')", "single"),
            ("![alt](a.jpg)", ""),
            ('![x](a.jpg "t"){width=50%}', "t"),
            ("no picture", ""),
        ],
    )
    def test_the_title_is_the_credit(self, body, credit) -> None:
        assert pa.parse_image_credit(body) == credit

    def test_the_credit_is_neither_alt_text_nor_body_text(self, images) -> None:
        body = f'![](pic.png "{URL}")\n\nUne phrase.'
        assert pa.parse_alt_text(body) == ""
        assert pa.parse_image(body, images) == (images / "pic.png").resolve()
        assert [it.text for it in pa.body_items(body)] == ["Une phrase."]


class TestLines:
    def test_a_short_credit_is_one_line_at_the_largest_size(self) -> None:
        assert pa.credit_lines(URL, 1000, "Satoshi") == (pa.CREDIT_SIZES[0], [URL])

    def test_a_long_credit_shrinks_then_breaks_after_a_slash_never_cut(self) -> None:
        size, lines = pa.credit_lines(URL, 200, "Satoshi")
        assert size == 9.0
        assert len(lines) == 2
        assert "".join(lines) == URL  # the whole address, nothing elided
        assert lines[0].endswith("/")
        assert "…" not in "".join(lines)
        assert not lines[0].endswith("https:/") and not lines[0].endswith("https://")

    def test_a_credit_without_a_slash_breaks_after_a_comma(self) -> None:
        text = "Courtesy of James S. Davis, US Navy, 1984, public domain, commons.wikimedia.org"
        size, lines = pa.credit_lines(text, 200, "Satoshi")
        assert size == pa.CREDIT_SIZES[-1] and len(lines) == 2
        assert lines[0].endswith(",") and not lines[1].startswith(" ")
        assert " ".join(lines) == text

    def test_a_medium_credit_shrinks_before_breaking(self) -> None:
        big = pa.CREDIT_SIZES[0]
        w = pa._text_width(URL, big, pa._face_metrics("Satoshi"))
        size, lines = pa.credit_lines(URL, w * 0.95, "Satoshi")
        assert size < big and lines == [URL]


def _assemble(md: str, layout: str, template: Path, images: Path, tmp_path: Path, index=1):
    catalog = pl.extract_layouts(template)
    slides = pl.segment(md)
    slides[index].chosen_layout = layout
    out = tmp_path / "out.pptx"
    pa.assemble(slides, catalog, template, out, image_base_dir=images, min_pt=30)
    return out, pptx.Presentation(str(out))


class TestPlacement:
    def test_a_lone_picture_gets_its_credit_bottom_right_inside_it(
        self, tmp_path, default_template, images
    ) -> None:
        md = f'# D\n\n## Une image\n\n![](pic.png "{URL}")\n\n## E\n'
        out, prs = _assemble(md, "Title Only", default_template, images, tmp_path)
        slide = prs.slides[1]
        (pic,) = _pictures(slide)
        (credit,) = _credits(slide)
        assert credit.text_frame.text == SHOWN
        assert _inside(_box(credit), _box(pic))
        # bottom right: closer to the picture's right and bottom edges than its left / top
        assert credit.left + credit.width > pic.left + pic.width - Inches(0.2)
        assert credit.top + credit.height > pic.top + pic.height - Inches(0.2)
        assert _sizes(credit) == {pa.CREDIT_SIZES[0]}
        run = credit.text_frame.paragraphs[0].runs[0]
        assert run.font.color.rgb == pa._WHITE and run.font.bold is False
        # the plate is translucent black, drawn above the picture
        assert credit.fill.fore_color.rgb == pptx.dml.color.RGBColor(0, 0, 0)
        assert b"alpha" in pptx.oxml.xmlchemy.serialize_for_reading(credit._element).encode()
        names = [sh.name for sh in slide.shapes]
        assert names.index(credit.name) > names.index(pic.name)
        # the credit is not the picture's description
        assert pic._element._nvXxPr.cNvPr.get("descr") != URL
        assert not [f for f in au.audit(out, min_pt=30) if f.shape == pa.CREDIT_NAME]
        assert not [f for f in au.audit(out, min_pt=30) if pa.CREDIT_NAME in f.detail]

    def test_without_a_title_there_is_no_credit(self, tmp_path, default_template, images) -> None:
        md = "# D\n\n## Une image\n\n![](pic.png)\n\n## E\n"
        _, prs = _assemble(md, "Title Only", default_template, images, tmp_path)
        assert not _credits(prs.slides[1])

    def test_a_full_bleed_photo_credits_clear_of_the_title_band(
        self, tmp_path, photo_template, images
    ) -> None:
        md = f'# D\n\n## Une chambre {{.photo}}\n\n![](pic.png "{URL}")\n\n## E\n'
        out, prs = _assemble(md, "Photo", photo_template, images, tmp_path)
        slide = prs.slides[1]
        (credit,) = _credits(slide)
        band = next(sh for sh in slide.shapes if sh.name == "band")
        assert not pa._intersects(_box(credit), _box(band))
        assert credit.top < prs.slide_height // 2  # moved to the top right
        assert credit.left + credit.width > prs.slide_width - Inches(0.3)
        names = [sh.name for sh in slide.shapes]
        assert names.index(credit.name) == len(names) - 1
        assert not [f for f in au.audit(out, min_pt=30) if f.shape == pa.CREDIT_NAME]

    def test_a_picture_in_a_column_is_credited_inside_its_own_box(
        self, tmp_path, default_template, images
    ) -> None:
        md = (
            "# D\n\n## Deux\n\n:::: {.columns}\n::: {.column}\n"
            f'![](pic.png "{URL}")\n:::\n::: {{.column}}\n- un\n- deux\n:::\n::::\n\n## E\n'
        )
        out, prs = _assemble(md, "Two Content", default_template, images, tmp_path)
        slide = prs.slides[1]
        (pic,) = _pictures(slide)
        (credit,) = _credits(slide)
        assert _inside(_box(credit), _box(pic))
        assert credit.text_frame.text == SHOWN
        assert not [f for f in au.audit(out, min_pt=30) if f.shape == pa.CREDIT_NAME]


class TestAudit:
    def test_only_the_credit_is_exempt(self, tmp_path, images) -> None:
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        pic = slide.shapes.add_picture(str(images / "pic.png"), Inches(1), Inches(1), Inches(4))
        pa.add_credit(slide, pic, URL)
        other = slide.shapes.add_textbox(Inches(1.2), Inches(1.2), Inches(2), Inches(0.4))
        other.text_frame.text = "petit"
        other.text_frame.paragraphs[0].runs[0].font.size = pptx.util.Pt(9)
        out = tmp_path / "a.pptx"
        prs.save(str(out))
        findings = au.audit(out, min_pt=30)
        assert not [f for f in findings if f.shape == pa.CREDIT_NAME]
        assert {"illegible-type", "under-min-pt"} <= {f.kind for f in findings if f.shape}


class TestPandocPath:
    def test_a_pandoc_deck_gets_its_credits_and_its_alt_text_back(self, tmp_path, images) -> None:
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        pic = slide.shapes.add_picture(str(images / "pic.png"), Inches(1), Inches(1), Inches(6))
        pic._element._nvXxPr.cNvPr.set("descr", f"{URL}\n\n/cache/pic.png")  # what Pandoc writes
        out = tmp_path / "pandoc.pptx"
        prs.save(str(out))
        assert pa.credit_pictures(out, f'## T\n\n![Un chien](pic.png "{URL}")\n') == 1
        slide = pptx.Presentation(str(out)).slides[0]
        (credit,) = _credits(slide)
        assert credit.text_frame.text == SHOWN
        (pic,) = _pictures(slide)
        assert pic._element._nvXxPr.cNvPr.get("descr") == "Un chien"

    def test_no_titles_leaves_the_deck_untouched(self, tmp_path) -> None:
        out = tmp_path / "x.pptx"
        pptx.Presentation().save(str(out))
        before = out.read_bytes()
        assert pa.credit_pictures(out, "## T\n\n![a](b.png)\n") == 0
        assert out.read_bytes() == before


class TestPreprocessingKeepsTheTitle:
    def test_absolutizing_a_path_leaves_the_credit_url_intact(self, tmp_path) -> None:
        from md2star.preprocessing.images import absolutize_image_paths, fix_image_widths

        md = f'![](sub/../pic.png "{URL}")'
        out = absolutize_image_paths(md, str(tmp_path))
        assert out == f'![]({(tmp_path / "pic.png")} "{URL}")'
        sized = fix_image_widths(out)
        assert f'"{URL}")' in sized and sized.endswith("}")

    def test_split_image_target(self) -> None:
        from md2star.preprocessing.images import split_image_target

        assert split_image_target("a.png") == ("a.png", "")
        assert split_image_target("my pic.png") == ("my pic.png", "")
        assert split_image_target(f'a.png "{URL}"') == ("a.png", f' "{URL}"')
        assert split_image_target("a.png 't'") == ("a.png", " 't'")


class TestShortCreditAndLinks:
    def test_the_credit_prints_the_site_and_keeps_the_full_address_as_link(self) -> None:
        assert pa.short_credit(URL) == (SHOWN, LINK)
        assert pa.short_credit("Photo maison") == ("Photo maison", None)

    def test_the_picture_and_the_credit_both_link_to_the_source(self, tmp_path) -> None:
        import pptx
        from PIL import Image

        img = tmp_path / "pic.png"
        Image.new("RGB", (400, 300), "gray").save(img)
        prs = pptx.Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[6])
        pic = slide.shapes.add_picture(str(img), 0, 0, prs.slide_width // 2, prs.slide_height // 2)
        tb = pa.add_credit(slide, pic, URL)
        assert pic.click_action.hyperlink.address == LINK
        run = tb.text_frame.paragraphs[0].runs[0]
        assert run.hyperlink.address == LINK
        assert run.font.italic is True
