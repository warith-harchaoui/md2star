"""Central logging surface for md2star.

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
separate is what lets ``md2star ... | some-tool`` keep working — a warning must
never land in the piped payload.

Every md2star module gets its logger from :func:`get_logger`, whose names are
dotted children of the root ``"md2star"`` logger (``md2star.cli``,
``md2star.preprocessing.lint``, ...). Because Python loggers propagate to
their ancestors, configuring the single ``"md2star"`` logger in
:func:`configure` wires up handler + level for the whole package at once.

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
import sys

# Root logger name for the whole package. Every module logger is a dotted
# child of this (e.g. "md2star.cli"), so configuring this one logger — and
# relying on logging's propagation up the name hierarchy — configures them all.
_ROOT_NAME: str = "md2star"

# Message format. Deliberately just the raw message: md2star's diagnostics
# already carry their own "md2star: " / "md2star warning: " prefixes (kept
# verbatim from the pre-logging ``print`` era so the on-screen UX is
# unchanged), and multi-line error hints must not get a per-line level prefix.
_FORMAT: str = "%(message)s"

# Marker attribute stamped on the handler we own, so :func:`configure` can be
# called repeatedly (PDF → DOCX re-entry, batch conversions in one process)
# without stacking duplicate handlers that would double-print every line.
_HANDLER_FLAG: str = "_md2star_owned"


class _LiveStderrHandler(logging.StreamHandler):
    """A :class:`~logging.StreamHandler` that always targets the *current* stderr.

    ``logging.StreamHandler`` binds ``sys.stderr`` once at construction. That
    breaks whenever ``sys.stderr`` is swapped afterwards — most notably under
    pytest's ``capsys`` fixture (which replaces the streams per test) and in
    any host that redirects stderr. Re-reading ``sys.stderr`` on every access
    keeps diagnostics flowing to wherever stderr currently points. This mirrors
    what :data:`logging.lastResort` does internally.

    Notes
    -----
    The ``stream`` setter is intentionally a no-op: the stream is not stored,
    it is computed live, so assignments (including the one in
    ``StreamHandler.__init__``) are simply ignored.
    """

    def __init__(self) -> None:
        # Let StreamHandler wire up formatter/lock machinery; the default
        # ``stream`` it tries to store is discarded by our setter below.
        super().__init__()

    @property
    def stream(self):  # type: ignore[override]
        """Return the live ``sys.stderr`` at emit time (never a stale handle)."""
        return sys.stderr

    @stream.setter
    def stream(self, value: object) -> None:
        # No-op on purpose — see the class docstring. We never cache a stream.
        pass


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
    """Configure the root ``"md2star"`` logger once, idempotently.

    Attaches exactly one stderr :class:`~logging.StreamHandler` and sets the
    threshold from the two mutually-exclusive verbosity flags.

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
    root = logging.getLogger(_ROOT_NAME)

    # Pick the threshold from the flags. ``quiet`` is the strongest signal,
    # then ``verbose``, then the behaviour-preserving INFO default.
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    root.setLevel(level)

    # Idempotency: only attach our stderr handler the first time. We recognise
    # our own handler by the marker attribute so a second call (or a handler
    # some host app added) never triggers a duplicate.
    already_installed = any(getattr(h, _HANDLER_FLAG, False) for h in root.handlers)
    if not already_installed:
        # Our own handler is what makes INFO-level progress visible: relying on
        # logging.lastResort alone would silently drop everything below WARNING.
        handler = _LiveStderrHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        # Stamp the marker so the check above finds it on subsequent calls.
        setattr(handler, _HANDLER_FLAG, True)
        root.addHandler(handler)

    # Keep propagation ON (the default). Our own handler already prints to
    # stderr once; because a handler *is* found in the hierarchy, lastResort
    # never fires, so there's no double-print in normal CLI use. Propagation
    # additionally lets a host application's / pytest's root handlers observe
    # md2star records (e.g. caplog in tests) — testability we want to keep.
    root.propagate = True
    return root
