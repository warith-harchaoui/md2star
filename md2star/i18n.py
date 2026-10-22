"""Message catalogues for the parts of md2star a person reads.

Two surfaces speak to a human: the CLI's diagnostics and the local GUI. They
were English-only, which for a tool whose documentation ships in two languages
was an odd place to stop.

The machinery is :class:`os_helper.Catalog`, the loader shared across the AI
Helpers suite — stdlib :mod:`gettext` underneath, with ``.po`` sources under
``md2star/data/locales/<lang>/LC_MESSAGES/`` compiled to the ``.mo`` it reads.
No Babel, no new dependency, and no build-time toolchain either:
``os_helper.compile_catalogs`` writes the ``.mo`` itself, because requiring GNU
gettext's ``msgfmt`` to be installed would make a translated interface harder
to ship than the feature is worth.

What stays here is the **policy**, which is md2star's and not the suite's.

**The CLI does not follow your shell locale, on purpose.** It answers to
``MD2STAR_LANG`` and nothing else. A converter that silently changes the
language of its own output because ``LANG`` says ``fr_FR`` is a converter that
breaks every script grepping it, and the diagnostics are as much a machine
interface as a human one. The GUI *does* negotiate ``Accept-Language``, because
a browser asking for French is a person asking, not an environment variable.

**The default is English, not French.** Every other member of the suite serves
a French GUI by default; md2star's CLI prints the language its *caller* asked
for and nothing else, so with no ``MD2STAR_LANG`` the answer must be the source
text. That is why this module keeps a policy layer rather than letting the call
sites reach for ``Catalog`` directly.

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
from functools import lru_cache
from pathlib import Path

import os_helper as osh

#: The gettext domain, and therefore the ``.mo`` file's stem.
DOMAIN = "md2star"

#: The one environment variable the CLI listens to. Deliberately ours rather
#: than ``LANG``: see the module docstring.
ENV_VAR = "MD2STAR_LANG"

#: The language the sources are written in, so it never needs a catalogue.
SOURCE_LANGUAGE = osh.gettext_utils.SOURCE_LANGUAGE


def locales_dir() -> Path:
    """Where the compiled catalogues live, inside the installed package."""
    # Next to the module rather than via importlib.resources: gettext wants a
    # real directory path, and md2star ships as an unzipped wheel (the same
    # assumption md2star.cli._data_path already documents and relies on).
    return Path(__file__).parent / "data" / "locales"


@lru_cache(maxsize=1)
def catalog() -> osh.Catalog:
    """The suite's shared catalogue loader, bound to this package.

    ``default_language`` is the **source** language, which is what makes an
    absent ``MD2STAR_LANG`` print English rather than French. The rest of the
    suite defaults its GUIs to French; a CLI that answers to its caller cannot.
    """
    return osh.Catalog.from_package(locales_dir(), DOMAIN, default_language=SOURCE_LANGUAGE)


def available() -> list[str]:
    """Languages with a compiled catalogue, sorted. English is implicit.

    Returns
    -------
    list of str
        The translated languages only. English is excluded even though
        :attr:`os_helper.Catalog.languages` includes it: it has no catalogue to
        be "available", and every caller here reads this as "languages somebody
        wrote a file for".
    """
    return [lang for lang in catalog().languages if lang != SOURCE_LANGUAGE]


def candidates(tag: str | None) -> list[str]:
    """A language tag plus its base, so ``fr-CA`` finds the ``fr`` catalogue.

    A thin alias for :func:`os_helper.language_candidates`, kept because this
    name is what md2star's own call sites and tests already use.
    """
    return osh.language_candidates(tag)


def translator(tag: str | None = None) -> _gettext.NullTranslations:
    """The catalogue for *tag*, or a pass-through when there is none.

    A tag with no catalogue yields a pass-through rather than a fallback
    language: here "no catalogue" means English, which is the source, so
    returning each message unchanged is exactly the right answer.
    """
    if not candidates(tag):
        return _gettext.NullTranslations()
    return catalog().translator_for(tag)


def ambient() -> _gettext.NullTranslations:
    """The CLI's catalogue, from :data:`ENV_VAR` alone."""
    # Read on every call rather than captured at import: a test (or a caller
    # driving md2star in-process) can change the language without reloading
    # the module, and the lookup behind it is cached anyway.
    return translator(os.environ.get(ENV_VAR))


def reset_cache() -> None:
    """Forget every resolved catalogue, so the next lookup reads afresh.

    The language is resolved from the environment on each call, but the
    *catalogue* behind it is cached — twice, once for the handle and once per
    language inside it. A test that writes a new ``.po`` mid-run, or changes
    which languages exist, needs both cleared or it reads the old answer.
    Changing ``MD2STAR_LANG`` alone does not: that is read every time.
    """
    catalog.cache_clear()
    osh.Catalog._translator.cache_clear()


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
    catalogue — both of which mean "leave the source text alone".
    """
    return catalog().negotiate(header)
