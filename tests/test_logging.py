"""Tests for the central logging surface (:mod:`md2star.logging`).

These pin the contracts PR-A relies on:

* :func:`get_logger` returns dotted children of the ``"md2star"`` root.
* :func:`configure` maps ``--verbose`` / ``--quiet`` to the right levels and
  is idempotent — repeated calls never stack handlers.
* The handler follows the *live* ``sys.stderr`` (so ``capsys`` sees output
  and stderr redirection works), which is why the CLI's diagnostics remain
  capturable after the print → logging migration, and prints the bare
  message (no level / logger decoration).

The ten original cases collapse into four functional scenarios: naming,
handler lifecycle (attach + idempotency), the parametrized level mapping,
and the stderr-routing / format contract exercised end-to-end.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import logging

import pytest

from md2star.logging import configure, get_logger

# md2star's ``configure`` delegates to ``os_helper.init_logging``, which stamps
# every handler it installs with this marker attribute — the seam these tests
# use to find "our" handler on the shared "md2star" logger.
_OWNED_FLAG = "_osh_owned"


@pytest.fixture(autouse=True)
def _reset_md2star_logger():
    """Restore the global ``"md2star"`` logger state around each test.

    Logging is process-global, so without this fixture one test's
    ``configure`` call would leak its handler + level into the next.
    """
    root = logging.getLogger("md2star")
    # Snapshot the pre-test state so we can restore it exactly.
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_propagate = root.propagate
    # Start each test from a clean slate: drop any handler we own.
    root.handlers = [h for h in saved_handlers if not getattr(h, _OWNED_FLAG, False)]
    yield
    # Restore verbatim.
    root.handlers = saved_handlers
    root.setLevel(saved_level)
    root.propagate = saved_propagate


def _owned_handlers() -> list[logging.Handler]:
    """Return the os_helper-installed handlers currently on the md2star logger."""
    root = logging.getLogger("md2star")
    return [h for h in root.handlers if getattr(h, _OWNED_FLAG, False)]


def test_get_logger_is_dotted_child() -> None:
    """A module logger is namespaced under the "md2star" root."""
    # An explicit dotted name is returned verbatim.
    assert get_logger("md2star.cli").name == "md2star.cli"
    # The default (no argument) is the root name itself.
    assert get_logger().name == "md2star"


def test_configure_installs_single_handler_and_is_idempotent() -> None:
    """The first configure() attaches one handler; repeats never stack more."""
    # First call installs exactly our single stderr handler.
    configure()
    assert len(_owned_handlers()) == 1

    # Two further calls with different flags must not duplicate the handler —
    # this is the idempotency guarantee the CLI relies on across sub-commands.
    configure(verbose=True)
    configure(quiet=True)
    assert len(_owned_handlers()) == 1


def test_configure_level_mapping() -> None:
    """Verbosity flags map to the documented thresholds; quiet outranks verbose."""
    for kwargs, expected in [
        ({}, logging.INFO),                                 # default
        ({"verbose": True}, logging.DEBUG),                 # --verbose: everything
        ({"quiet": True}, logging.ERROR),                   # --quiet: errors only
        ({"verbose": True, "quiet": True}, logging.ERROR),  # quiet wins
    ]:
        configure(**kwargs)
        # The root level gates every child logger's records.
        assert logging.getLogger("md2star").level == expected


def test_output_routes_to_live_stderr_bare_and_level_gated(capsys) -> None:
    """Records reach the *current* stderr, unadorned, and obey the level gate.

    This exercises three intertwined contracts in one realistic run:

    * The handler re-reads ``sys.stderr`` on each emit, so ``capsys`` (which
      swapped stderr after import) still captures the output.
    * The format is message-only — no ``"ERROR md2star.test:"`` decoration —
      preserving the pre-migration on-screen UX.
    * ``--quiet`` suppresses warnings/info yet still surfaces errors.
    """
    # Under --quiet, INFO/WARNING are dropped but ERROR survives.
    configure(quiet=True)
    log = get_logger("md2star.test")
    log.warning("this warning should be hidden")
    log.error("md2star: bare message")
    err = capsys.readouterr().err
    # The warning was gated out by the ERROR threshold.
    assert "this warning should be hidden" not in err
    # The error reached live stderr, printed verbatim with no prefix/suffix.
    assert err == "md2star: bare message\n"
