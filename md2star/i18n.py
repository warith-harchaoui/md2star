"""Message catalogues for the parts of md2star a person reads.

Two surfaces speak to a human: the CLI's diagnostics and the local GUI. They
were English-only, which for a tool whose documentation ships in two languages
was an odd place to stop.

The runtime is stdlib :mod:`gettext` — ``.po`` sources under
``md2star/data/locales/<lang>/LC_MESSAGES/``, compiled to the ``.mo`` the
module reads. No Babel, no new dependency, and no build-time toolchain either:
``scripts/compile_catalogs.py`` writes the ``.mo`` itself, because requiring
GNU gettext's ``msgfmt`` to be installed would make a translated interface
harder to ship than the feature is worth.

**The CLI does not follow your shell locale, on purpose.** It answers to
``MD2STAR_LANG`` and nothing else. A converter that silently changes the
language of its own output because ``LANG`` says ``fr_FR`` is a converter that
breaks every script grepping it, and the diagnostics are as much a machine
interface as a human one. The GUI *does* negotiate ``Accept-Language``, because
a browser asking for French is a person asking, not an environment variable.

A message with no translation falls back to the English source — gettext's own
behaviour — so a partial catalogue leaves an interface that is partly
translated rather than one that is broken.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import gettext as _gettext
import os
import re
from functools import lru_cache
from pathlib import Path

#: The gettext domain, and therefore the ``.mo`` file's stem.
DOMAIN = "md2star"

#: The one environment variable the CLI listens to. Deliberately ours rather
#: than ``LANG``: see the module docstring.
ENV_VAR = "MD2STAR_LANG"

#: One ``q``-weighted entry of an ``Accept-Language`` header.
_ACCEPT_RE = re.compile(r"\s*([A-Za-z-]+|\*)\s*(?:;\s*q\s*=\s*([0-9.]+))?\s*")


def locales_dir() -> Path:
    """Where the compiled catalogues live, inside the installed package."""
    # Next to the module rather than via importlib.resources: gettext wants a
    # real directory path, and md2star ships as an unzipped wheel (the same
    # assumption md2star.cli._data_path already documents and relies on).
    return Path(__file__).parent / "data" / "locales"


def available() -> list[str]:
    """Languages with a compiled catalogue, sorted. English is implicit."""
    root = locales_dir()
    if not root.is_dir():
        # A source checkout whose catalogues have never been compiled: no
        # languages, no error. English is always available without a file.
        return []
    return sorted(d.name for d in root.iterdir() if (d / "LC_MESSAGES" / f"{DOMAIN}.mo").is_file())


def candidates(tag: str | None) -> list[str]:
    """A language tag plus its base, so ``fr-CA`` finds the ``fr`` catalogue.

    Normalised the way gettext names directories (``fr_CA``, not ``fr-CA``),
    and stripped of any ``.UTF-8`` / ``@euro`` suffix a locale string carries.
    """
    if not tag:
        return []
    # BCP 47 writes `fr-CA`, POSIX locales write `fr_CA.UTF-8@euro`, and
    # gettext's directories are named like the second. One normalisation here
    # means both an HTTP header and an environment variable can be passed in.
    cleaned = tag.strip().replace("-", "_").split(".")[0].split("@")[0]
    if not cleaned:
        return []
    # Region first, then the bare language: a Québécois browser should get the
    # French catalogue rather than nothing when `fr_CA` does not exist.
    base = cleaned.split("_")[0]
    return [cleaned, base] if base != cleaned else [cleaned]


@lru_cache(maxsize=8)
def translator(tag: str | None = None) -> _gettext.NullTranslations:
    """The catalogue for *tag*, or a pass-through when there is none.

    Cached: a catalogue is a file read, and the GUI resolves one per request.
    """
    wanted = candidates(tag)
    if not wanted:
        return _gettext.NullTranslations()
    try:
        return _gettext.translation(DOMAIN, localedir=str(locales_dir()), languages=wanted)
    except OSError:
        # No catalogue for that language is not an error: English is the
        # source, so a pass-through is exactly the right answer.
        return _gettext.NullTranslations()


def ambient() -> _gettext.NullTranslations:
    """The CLI's catalogue, from :data:`ENV_VAR` alone."""
    # Read on every call rather than captured at import: a test (or a caller
    # driving md2star in-process) can change the language without reloading
    # the module, and the lookup behind it is cached anyway.
    return translator(os.environ.get(ENV_VAR))


def gettext(message: str) -> str:
    """Translate *message* for the CLI's ambient language.

    Named to read as ``_()`` at the call site::

        from .i18n import gettext as _
        print(_("Wrote: %s") % path)
    """
    return ambient().gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Plural-aware lookup — ``n`` picks the form the language actually uses."""
    return ambient().ngettext(singular, plural, n)


def negotiate(header: str | None) -> str | None:
    """Best language from an ``Accept-Language`` header, or ``None``.

    Honours ``q`` weights and falls back to a base language, so a browser
    asking for ``fr-CA;q=0.9, en;q=0.8`` gets the ``fr`` catalogue. Returns
    ``None`` when the best match is English or when nothing offered has a
    catalogue — both mean "leave the source text alone".

    English counts as *offered* even though it has no catalogue, and that is
    not a technicality: without it, a visitor who asked for English first and
    French second would be served French, because the language they actually
    wanted was the one the loop could not see.
    """
    if not header:
        return None
    offered = set(available()) | {"en"}
    if offered == {"en"}:
        return None
    # Parsed by hand rather than with a header library: this is one header,
    # the grammar is a list of tags with optional q weights, and md2star does
    # not take a dependency for forty lines of standard parsing.
    ranked: list[tuple[float, int, str]] = []
    for order, part in enumerate(header.split(",")):
        match = _ACCEPT_RE.fullmatch(part)
        if not match or match.group(1) == "*":
            continue
        try:
            quality = float(match.group(2)) if match.group(2) else 1.0
        except ValueError:
            # A malformed q value is a browser's problem, not a reason to
            # refuse the language: treat it as the default weight.
            quality = 1.0
        # `order` breaks ties the way the header's own sequence intends, and
        # negating quality sorts strongest-first with a plain ascending sort.
        ranked.append((-quality, order, match.group(1)))
    for _quality, _order, tag in sorted(ranked):
        for candidate in candidates(tag):
            if candidate in offered:
                return None if candidate.split("_")[0] == "en" else candidate
    return None
