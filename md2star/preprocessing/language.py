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
    try:
        import langdetect
    except ImportError:
        return None

    text = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

    try:
        lang_code = langdetect.detect(text)
    except Exception:
        return None

    return _LANG_MAPPING.get(
        lang_code,
        {"lang": lang_code, "date_format": "%A, %e %B %Y"},
    )
