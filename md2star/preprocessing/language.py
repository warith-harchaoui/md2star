"""Language detection and ``lang`` / ``date_format`` metadata mapping.

A best-effort guess via the ``langdetect`` package; returns ``None`` when
``langdetect`` is unavailable so the caller can skip metadata injection
without crashing.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import re

# Detected two-letter language → Pandoc BCP-47 ``lang`` + a strftime
# ``date_format`` matching that locale's conventional long date. The format
# strings are what the Lua filter feeds to strftime for the auto-dated
# subtitle, so each is hand-tuned to the language (e.g. day-before-month in
# French/Spanish, CJK ``年月日`` ordering). Region choices (en-US, pt-BR) reflect
# md2star's most common audiences.
_LANG_MAPPING: dict[str, dict[str, str]] = {
    "en": {"lang": "en-US", "date_format": "%A, %B %e, %Y"},
    "fr": {"lang": "fr-FR", "date_format": "%A %e %B %Y"},
    "es": {"lang": "es-ES", "date_format": "%A, %e de %B de %Y"},
    "de": {"lang": "de-DE", "date_format": "%A, %e. %B %Y"},
    "it": {"lang": "it-IT", "date_format": "%A %e %B %Y"},
    "pt": {"lang": "pt-BR", "date_format": "%A, %e de %B de %Y"},
    "nl": {"lang": "nl-NL", "date_format": "%A %e %B %Y"},
    "ru": {"lang": "ru-RU", "date_format": "%A, %e %B %Y"},
    "zh-cn": {"lang": "zh-CN", "date_format": "%Y年%m月%d日"},
    "ja": {"lang": "ja-JP", "date_format": "%Y年%m月%d日"},
}


def get_language_metadata(content: str) -> dict | None:
    """Return ``{'lang': ..., 'date_format': ...}`` or ``None``.

    Strips fenced code blocks, HTML tags, and link targets before detection so
    only prose is fed to the language guesser.
    """
    # langdetect is an optional dependency: if it's absent we return None so
    # the caller silently skips language metadata rather than crashing.
    try:
        import langdetect
    except ImportError:
        return None

    # Strip non-prose before detection — code, HTML, and link *targets* are
    # often English-ish noise that skews the guess. We keep link *text*
    # (the \1 backref) because that's real prose in the document's language.
    text = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    # detect() raises on empty/undetectable input; treat that as "unknown".
    try:
        lang_code = langdetect.detect(text)
    except Exception:
        return None

    # Known languages get their tuned mapping; anything else still gets a
    # usable fallback (the raw code + a neutral long-date format) rather than
    # nothing, so unusual languages don't lose their date subtitle entirely.
    return _LANG_MAPPING.get(
        lang_code,
        {"lang": lang_code, "date_format": "%A, %e %B %Y"},
    )
