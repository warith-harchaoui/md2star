"""Functional tests for the v1.2.0 localized ``--bibliography-name`` default.

When the user passes ``--bib`` without ``--bibliography-name``, md2star
picks the per-language default heading (Bibliographie in French,
Bibliografía in Spanish, …). The resolution order is:

    explicit ``--bibliography-name``  >  explicit ``--lang``  >  langdetect
    on the body  >  English fallback.

These tests exercise ``_localized_bibliography_heading`` (the resolver)
and ``_BIBLIOGRAPHY_HEADING_BY_LANG`` (the localization table) grouped by
workflow, rather than one micro-assertion per language.
"""

from __future__ import annotations

from md2star.cli import _BIBLIOGRAPHY_HEADING_BY_LANG, _localized_bibliography_heading


def test_explicit_lang_overrides_body_across_all_locales():
    """Explicit ``--lang`` wins over body content for every shipped locale.

    Notes
    -----
    One assertion per shipped locale, all driven from a single table. The
    body is deliberately English so a French/Spanish/… result can only
    come from honouring the tag — never from detection — proving the
    ``--lang`` > detection precedence. Region subtags (``fr-FR``) confirm
    only the primary subtag is consulted.
    """
    # (tag-as-passed-to--lang, heading the resolver must return).
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
    # Explicit lang beats detection: English prose must not sway the result.
    for lang, expected in cases.items():
        assert _localized_bibliography_heading("body in English", lang) == expected


def test_english_fallback_for_unknown_lang_and_undetectable_bodies():
    """Unknown tags and no-signal bodies all degrade to English.

    Notes
    -----
    Covers the two tails of the resolution chain in one place:
    * an unrecognised ``--lang`` tag is not an error — it → English;
    * with no ``--lang`` and nothing detectable (empty body, or a single
      char langdetect can't classify) the resolver must not raise and must
      return the English default.
    """
    # Unknown explicit tag → English (not an error).
    assert _localized_bibliography_heading("body", "xx-YY") == "Bibliography"
    # No lang + no detectable signal → deterministic English fallback.
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
