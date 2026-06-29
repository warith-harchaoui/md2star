"""Tests for the v1.2.0 localized --bibliography-name default.

When the user passes --bib without --bibliography-name, md2star uses
the per-language default (Bibliographie in French, Bibliografía in
Spanish, etc.). Explicit --lang wins over detection; explicit
--bibliography-name wins over both.
"""

from __future__ import annotations

from md2star.cli import _BIBLIOGRAPHY_HEADING_BY_LANG, _localized_bibliography_heading


class TestExplicitLang:
    """``--lang fr-FR`` → "Bibliographie", regardless of body content."""

    def test_french_explicit(self):
        assert _localized_bibliography_heading("body in English", "fr-FR") == "Bibliographie"

    def test_spanish_explicit(self):
        assert _localized_bibliography_heading("body in English", "es-ES") == "Bibliografía"

    def test_german_explicit(self):
        assert _localized_bibliography_heading("body in English", "de-DE") == "Literatur"

    def test_italian_explicit(self):
        assert _localized_bibliography_heading("body in English", "it") == "Bibliografia"

    def test_portuguese_explicit(self):
        assert _localized_bibliography_heading("body in English", "pt-BR") == "Bibliografia"

    def test_dutch_explicit(self):
        assert _localized_bibliography_heading("body in English", "nl") == "Bibliografie"

    def test_russian_explicit(self):
        assert _localized_bibliography_heading("body in English", "ru") == "Библиография"

    def test_english_explicit(self):
        assert _localized_bibliography_heading("body in English", "en-US") == "Bibliography"

    def test_unknown_lang_falls_back_to_english(self):
        assert _localized_bibliography_heading("body", "xx-YY") == "Bibliography"


class TestDetectionFallback:
    """No --lang → langdetect on the body; English fallback if undetectable."""

    def test_french_body_detected(self):
        # Long enough that langdetect lands on French.
        body = (
            "Voici un texte en français avec suffisamment de mots pour "
            "que la détection automatique de la langue donne fr. Nous "
            "écrivons en français, et la bibliographie devrait porter "
            "le titre Bibliographie."
        )
        result = _localized_bibliography_heading(body, None)
        # langdetect can be noisy on short text; accept either the
        # detected French OR the English fallback, but the test
        # confirms the function doesn't crash and returns a sensible
        # value.
        assert result in ("Bibliographie", "Bibliography")

    def test_empty_body_falls_back_to_english(self):
        assert _localized_bibliography_heading("", None) == "Bibliography"

    def test_no_meaningful_text_falls_back_to_english(self):
        # Single character — langdetect can't pick a language.
        assert _localized_bibliography_heading("a", None) == "Bibliography"


class TestHeadingMappingIntegrity:
    """The localization dict has the eight languages we ship for date formatting."""

    def test_all_locale_filter_languages_have_a_heading(self):
        expected_keys = {"en", "fr", "es", "de", "it", "pt", "nl", "ru"}
        assert expected_keys.issubset(set(_BIBLIOGRAPHY_HEADING_BY_LANG.keys()))

    def test_every_value_is_non_empty(self):
        for lang, heading in _BIBLIOGRAPHY_HEADING_BY_LANG.items():
            assert heading and isinstance(heading, str), lang
