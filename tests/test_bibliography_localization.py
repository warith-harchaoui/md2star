"""Functional tests for the v1.2.0 localized ``--bibliography-name`` default.

When the user passes ``--bib`` without ``--bibliography-name``, md2star
picks the per-language default heading (Bibliographie in French,
Bibliografía in Spanish, …). The resolution order is:

    explicit ``--bibliography-name``  >  explicit ``--lang``  >  langdetect
    on the body  >  English fallback.

These tests exercise ``_localized_bibliography_heading`` (the resolver)
and ``_BIBLIOGRAPHY_HEADING_BY_LANG`` (the localization table) grouped by
workflow, rather than one micro-assertion per language.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

from md2star.cli import _BIBLIOGRAPHY_HEADING_BY_LANG, _localized_bibliography_heading


def test_explicit_lang_precedence_and_english_fallback():
    """Explicit ``--lang`` wins over body content, and the tails degrade to English.

    One place for the whole precedence rule: every shipped locale resolves from
    the tag (English prose must not sway it, proving ``--lang`` > detection, and
    region subtags like ``fr-FR`` consult only the primary subtag); an unknown
    tag and no-signal bodies (empty / single char) all degrade to English
    without raising.
    """
    # Explicit lang beats detection for every shipped locale.
    cases = {
        "fr-FR": "Bibliographie",
        "es-ES": "Bibliografía",
        "de-DE": "Literatur",
        "it": "Bibliografia",
        "pt-BR": "Bibliografia",
        "nl": "Bibliografie",
        "ru": "Библиография",
        "en-US": "Bibliography",
    }
    for lang, expected in cases.items():
        assert _localized_bibliography_heading("body in English", lang) == expected

    # The tails of the chain all degrade to English (never an error).
    assert _localized_bibliography_heading("body", "xx-YY") == "Bibliography"
    assert _localized_bibliography_heading("", None) == "Bibliography"
    assert _localized_bibliography_heading("a", None) == "Bibliography"


def test_detection_from_body_is_sensible_and_never_crashes():
    """A French body with no ``--lang`` detects French (or safely falls back).

    Notes
    -----
    langdetect is stochastic on short input, so we pin the *contract*
    rather than a single value: the result is either the correctly
    detected French heading or the English fallback — and, critically,
    the resolver returns without raising. This is the only test that
    exercises the langdetect branch end-to-end.
    """
    body = (
        "Voici un texte en français avec suffisamment de mots pour "
        "que la détection automatique de la langue donne fr. Nous "
        "écrivons en français, et la bibliographie devrait porter "
        "le titre Bibliographie."
    )
    # Detection path is exercised (lang=None) and must yield a sane value.
    result = _localized_bibliography_heading(body, None)
    assert result in ("Bibliographie", "Bibliography")


def test_localization_table_is_complete_and_well_formed():
    """The heading table covers every date locale with non-empty strings.

    Notes
    -----
    Two integrity guards on the shared table:
    * it stays in lock-step with the date-localization filter — a heading
      exists for each of the eight locales md2star can localize dates for;
    * no locale maps to a blank / non-string heading, which would inject
      an empty ``## `` into the output document.
    """
    # Every date-formatting locale must have a bibliography heading too.
    expected_keys = {"en", "fr", "es", "de", "it", "pt", "nl", "ru"}
    assert expected_keys.issubset(set(_BIBLIOGRAPHY_HEADING_BY_LANG.keys()))
    # A blank heading would emit an empty "## " into the output document.
    for lang, heading in _BIBLIOGRAPHY_HEADING_BY_LANG.items():
        assert heading and isinstance(heading, str), lang
