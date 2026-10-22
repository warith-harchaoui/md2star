"""Message catalogues: resolution, plurals, the GUI pass, and the two policies.

The policies are the part worth pinning, because they are decisions rather
than mechanics:

* the **CLI** answers to ``MD2STAR_LANG`` and ignores ``LANG`` entirely, so a
  French shell does not silently change the language of output that scripts
  grep;
* the **GUI** honours ``Accept-Language``, because a browser asking for French
  is a person asking;
* a message with **no translation keeps its English source**, so an unfinished
  catalogue leaves a partly translated interface rather than a broken one.

The ``.mo`` compiler is checked against Python's own ``gettext`` reader rather
than against a fixture of expected bytes: the format is only correct if the
stdlib can read it back.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

from md2star import i18n

_ROOT = Path(__file__).resolve().parents[1]


def _compiler():
    """Import `scripts/compile_catalogs.py`, which is not an installed module."""
    spec = importlib.util.spec_from_file_location(
        "compile_catalogs", _ROOT / "scripts" / "compile_catalogs.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["compile_catalogs"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _clear_cache():
    """The translator is cached per tag; these tests change the environment."""
    i18n.reset_cache()
    yield
    i18n.reset_cache()


class TestLanguageResolution:
    def test_a_regional_tag_finds_the_base_catalogue(self) -> None:
        assert i18n.candidates("fr-CA") == ["fr_CA", "fr"]
        assert i18n.candidates("fr_FR.UTF-8@euro") == ["fr_FR", "fr"]
        assert i18n.candidates(None) == [] and i18n.candidates("  ") == []

    def test_the_cli_ignores_the_shell_locale(self, monkeypatch) -> None:
        """A script grepping md2star's output must not depend on $LANG."""
        monkeypatch.setenv("LANG", "fr_FR.UTF-8")
        monkeypatch.delenv(i18n.ENV_VAR, raising=False)
        assert i18n.gettext("layout audit: clean") == "layout audit: clean"
        monkeypatch.setenv(i18n.ENV_VAR, "fr")
        i18n.reset_cache()
        assert i18n.gettext("layout audit: clean") != "layout audit: clean"

    def test_an_unknown_language_falls_back_to_english(self, monkeypatch) -> None:
        monkeypatch.setenv(i18n.ENV_VAR, "xx")
        assert i18n.gettext("layout audit: clean") == "layout audit: clean"

    def test_french_is_shipped_compiled(self) -> None:
        assert "fr" in i18n.available()


class TestAcceptLanguage:
    def test_quality_weights_decide(self) -> None:
        assert i18n.negotiate("fr-CA;q=0.9, en;q=0.8") == "fr"
        assert i18n.negotiate("en;q=0.9, fr;q=0.8") is None  # English is the source
        assert i18n.negotiate("de, ja;q=0.5") is None
        assert i18n.negotiate(None) is None and i18n.negotiate("*") is None


class TestCatalogueCompiler:
    def test_what_it_writes_is_what_gettext_reads(self, tmp_path: Path) -> None:
        import gettext as stdlib_gettext

        compiler = _compiler()
        po = tmp_path / "x.po"
        po.write_text(
            'msgid ""\nmsgstr "Content-Type: text/plain; charset=UTF-8\\n"\n'
            '"Plural-Forms: nplurals=2; plural=(n > 1);\\n"\n\n'
            'msgid "one slide"\nmsgstr "une diapositive"\n\n'
            'msgid "%(n)d finding"\nmsgid_plural "%(n)d findings"\n'
            'msgstr[0] "%(n)d constat"\nmsgstr[1] "%(n)d constats"\n',
            encoding="utf-8",
        )
        target = tmp_path / "fr" / "LC_MESSAGES"
        target.mkdir(parents=True)
        (target / "md2star.mo").write_bytes(compiler.build_mo(compiler.parse_po(po)))
        catalogue = stdlib_gettext.translation("md2star", localedir=str(tmp_path), languages=["fr"])
        assert catalogue.gettext("one slide") == "une diapositive"
        assert catalogue.ngettext("%(n)d finding", "%(n)d findings", 1) == "%(n)d constat"
        assert catalogue.ngettext("%(n)d finding", "%(n)d findings", 4) == "%(n)d constats"

    def test_an_untranslated_entry_is_left_to_fall_back(self, tmp_path: Path) -> None:
        compiler = _compiler()
        po = tmp_path / "x.po"
        po.write_text('msgid "untouched"\nmsgstr ""\n', encoding="utf-8")
        assert "untouched" not in compiler.parse_po(po)

    def test_the_shipped_catalogue_is_not_stale(self) -> None:
        """A translation edited without recompiling would ship looking live."""
        compiler = _compiler()
        assert compiler.main(["--check", "--root", str(_ROOT / "md2star/data/locales")]) == 0


class TestTheTranslatedSurfaces:
    def test_the_audit_summary_speaks_french_on_request(self, monkeypatch) -> None:
        from md2star.pptx_audit import Finding, summarise

        monkeypatch.setenv(i18n.ENV_VAR, "fr")
        i18n.reset_cache()
        line = summarise([Finding(3, "overlap", "x"), Finding(3, "overrun", "y")], slides=6)
        assert "2 constats" in line and "1 diapositive" in line
        # The finding kinds are the closed machine vocabulary and stay English:
        # they are what a caller greps and what a bug report quotes.
        assert "overlap" in line and "overrun" in line

    def test_a_finding_reads_in_french_without_losing_its_kind(self, monkeypatch) -> None:
        from md2star.pptx_audit import Finding

        monkeypatch.setenv(i18n.ENV_VAR, "fr")
        i18n.reset_cache()
        line = str(Finding(3, "off-slide", "…", "Title 1"))
        assert line.startswith("diapositive 3 : off-slide [Title 1]")

    def test_the_gui_page_is_served_in_the_visitors_language(self) -> None:
        from md2star import gui_server

        html = '<html lang="en" class="h-full">…Markdown editor…Render…'
        translated = gui_server.localise(html, "fr-FR,fr;q=0.9")
        assert 'lang="fr"' in translated
        assert "Éditeur Markdown" in translated and "Convertir" in translated
        # No preference this server can honour leaves the page exactly as it is.
        assert gui_server.localise(html, "de") == html
        assert gui_server.localise(html, None) == html

    def test_every_string_the_gui_claims_to_translate_is_still_in_the_page(self) -> None:
        """Stops the declared list from rotting while the interface moves on."""
        from md2star import gui_server

        page = (_ROOT / "md2star/data/gui/index.html").read_text(encoding="utf-8")
        missing = [source for source in gui_server.UI_STRINGS if source not in page]
        assert missing == []

    def test_an_error_carries_its_hint_into_french(self, monkeypatch) -> None:
        """Both halves of the two-block message, including the class default."""
        from md2star.errors import InvalidInputError, MissingDependencyError

        monkeypatch.setenv(i18n.ENV_VAR, "fr")
        i18n.reset_cache()
        explicit = InvalidInputError(
            "md2pptx: --reference-slides only applies to --smart-layout",
            hint="Add --smart-layout --template <designer.pptx>, or drop --reference-slides.",
        )
        assert "ne s'applique qu'à" in str(explicit)
        assert "Ajoutez --smart-layout" in explicit.hint
        # A class default is a string frozen at import; it has to be looked up
        # when the error is raised, not when the module loads.
        assert "md2star doctor" in MissingDependencyError("x").hint
        assert MissingDependencyError("x").hint.startswith("Lancez")

    def test_an_interpolated_message_still_reads_in_french(self, monkeypatch) -> None:
        from md2star.errors import InvalidInputError
        from md2star.i18n import gettext as translate

        monkeypatch.setenv(i18n.ENV_VAR, "fr")
        i18n.reset_cache()
        message = translate("md2%(fmt)s: input file not found: %(path)s") % {
            "fmt": "pptx",
            "path": "/nope.md",
        }
        assert (
            str(InvalidInputError(message)) == "md2pptx : fichier d'entrée introuvable : /nope.md"
        )

    def test_doctor_reads_in_french_while_its_json_stays_english(self, monkeypatch) -> None:
        """The report is data as well as prose, and only the prose moves."""
        from md2star import doctor

        monkeypatch.setenv(i18n.ENV_VAR, "fr")
        i18n.reset_cache()
        report = doctor.run_checks()
        text = doctor.render(report)
        assert "Essentiel :" in text and "Résultat :" in text and "Export DOCX" in text
        # The section names double as dictionary keys and the statuses are
        # tokens a script greps: both stay English in the data itself.
        assert {c.section for c in report.checks} <= {"Core", "Optional", "Templates"}
        assert all(c.status.isupper() for c in report.checks)


def test_the_declared_os_helper_floor_carries_the_catalog_api() -> None:
    """This module delegates to `osh.Catalog`; a lower floor is a lie.

    `Catalog` landed in os-helper 2.6.0 and `negotiate` / `ngettext` /
    region-fallback in 2.8.0, all of which `i18n.py` now calls. Neither CI nor
    a developer machine would catch a wrong declaration: pip resolves the
    NEWEST os-helper, never the floor, so it can be wrong for months without a
    single red build and break only for whoever pins.

    Read with a regex rather than `tomllib`: this package supports Python
    3.10, where `tomllib` is not in the standard library, and a test that
    errors on the floor of the supported range is not a test.
    """
    text = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    bound = re.search(r'"os-helper>=(\d+)\.(\d+)(?:\.(\d+))?', text)
    assert bound, "pyproject.toml declares no os-helper lower bound"
    floor = tuple(int(part or 0) for part in bound.groups())
    assert floor >= (2, 8, 0), (
        f"declared floor {bound.group(0)!r} predates Catalog.negotiate (2.8.0)"
    )


def test_the_shared_loader_is_what_resolves_the_strings() -> None:
    """One gettext implementation in the suite, not two.

    md2star carried its own `.po` parser, `.mo` writer and language
    negotiation until 3.9.0. This pins the delegation so a future edit cannot
    quietly grow a second copy back.
    """
    import os_helper as osh

    assert isinstance(i18n.catalog(), osh.Catalog)
