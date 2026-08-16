"""Central logging surface for md2star (backed by os_helper).

Module summary
--------------
Historically md2star scattered ``print(..., file=sys.stderr)`` diagnostics
across the CLI and the preprocessing modules. This module replaces them with
a single, centrally-configured :mod:`logging` surface so verbosity is
controlled from one place (``--verbose`` / ``--quiet``) rather than hard-wired
at every call site.

The split it enforces is deliberate: **diagnostics** (warnings, errors,
progress narration) go through this logging surface to *stderr*, while program
**output** (a rendered document path, the ``doctor --json`` payload, the
``templates list`` table) stays on ``print``/*stdout*. Keeping the two streams
separate is what lets ``md2star ... | some-tool`` keep working, a warning must
never land in the piped payload.

The actual logging setup is delegated to :func:`os_helper.init_logging`, the
suite's shared logging primitive, in its CLI-friendly mode: a *named* logger
(``"md2star"``), a bare ``%(message)s`` format, a **live** stderr handler that
re-resolves ``sys.stderr`` on each emit (so pytest's ``capsys`` and any stream
redirection keep working), idempotent so repeated calls never double-print, and
``propagate=True`` so ``caplog`` and host applications still observe records.
Every md2star module gets its logger from :func:`get_logger`, whose names are
dotted children of ``"md2star"`` (``md2star.cli``, ``md2star.preprocessing.lint``,
…) and therefore inherit that configuration.

Usage example
-------------
>>> from md2star.logging import configure, get_logger
>>> configure(verbose=False, quiet=False)   # once, at CLI startup
>>> log = get_logger(__name__)
>>> log.warning("md2star: falling back to the bundled template")

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

# NOTE: this module is named ``logging`` but ``import logging`` below resolves
# to the *standard library* module, not to this file. Python 3 uses absolute
# imports by default, so ``import logging`` is keyed as ``"logging"`` in
# ``sys.modules`` while this file is ``"md2star.logging"`` — no shadowing.
import logging

import os_helper as osh

# Root logger name for the whole package. Every module logger is a dotted
# child of this (e.g. "md2star.cli"), so configuring this one logger — and
# relying on logging's propagation up the name hierarchy — configures them all.
_ROOT_NAME: str = "md2star"

# Message format. Deliberately just the raw message: md2star's diagnostics
# already carry their own "md2star: " / "md2star warning: " prefixes (kept
# verbatim from the pre-logging ``print`` era so the on-screen UX is
# unchanged), and multi-line error hints must not get a per-line level prefix.
_FORMAT: str = "%(message)s"


def get_logger(name: str = _ROOT_NAME) -> logging.Logger:
    """Return the md2star logger for *name*.

    Parameters
    ----------
    name : str, optional
        Logger name. Pass ``__name__`` from a module so the returned logger is
        a dotted child of ``"md2star"`` (the default) and inherits the level +
        handler installed by :func:`configure`.

    Returns
    -------
    logging.Logger
        The per-name singleton logger (``logging.getLogger`` caches by name).

    Examples
    --------
    >>> get_logger("md2star.cli").name
    'md2star.cli'
    """
    # logging.getLogger already memoizes by name, so no caching is needed here.
    return logging.getLogger(name)


def configure(*, verbose: bool = False, quiet: bool = False) -> logging.Logger:
    """Configure the root ``"md2star"`` logger once, idempotently, via os_helper.

    Delegates to :func:`os_helper.init_logging` in its named-logger + live-stderr
    mode, which attaches exactly one stderr handler and re-resolves ``sys.stderr``
    on each emit (so ``capsys`` / redirection keep working). Repeated calls are a
    no-op on the handler set, so re-entry (PDF → DOCX, batch conversions) never
    double-prints.

    Parameters
    ----------
    verbose : bool, optional
        When true, lower the threshold to ``DEBUG`` (show everything).
    quiet : bool, optional
        When true, raise the threshold to ``ERROR`` (suppress info + warnings).
        ``quiet`` wins if, defensively, both flags are set.

    Returns
    -------
    logging.Logger
        The configured root md2star logger (handy for tests and callers).

    Notes
    -----
    The default level (neither flag) is ``INFO`` so that every message that
    used to be printed unconditionally in the ``print`` era stays visible —
    this migration is behaviour-preserving by default. Diagnostics always go
    to *stderr* so they never contaminate stdout output.
    """
    # Pick the threshold from the flags. ``quiet`` is the strongest signal,
    # then ``verbose``, then the behaviour-preserving INFO default.
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    # os_helper owns the handler machinery for the whole suite. The kwargs pin
    # md2star's CLI contract: the "md2star" tree, bare stderr output, a live
    # stream (capsys-safe), no ANSI coloring of the bare line, no warnings
    # capture (we route our own), and propagate=True so caplog / host apps see
    # our records. init_logging is idempotent for a named logger, so calling
    # configure() again never stacks a duplicate handler.
    return osh.init_logging(
        name=_ROOT_NAME,
        level=level,
        stdout=False,
        log_format=_FORMAT,
        use_colors=False,
        capture_warnings=False,
        live_stream=True,
        propagate=True,
    )
