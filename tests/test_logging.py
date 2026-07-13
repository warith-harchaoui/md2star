"""Tests for the central logging surface (:mod:`md2star.logging`).

These pin the contracts PR-A relies on:

* :func:`get_logger` returns dotted children of the ``"md2star"`` root.
* :func:`configure` maps ``--verbose`` / ``--quiet`` to the right levels.
* :func:`configure` is idempotent — repeated calls never stack handlers.
* The handler follows the *live* ``sys.stderr`` (so ``capsys`` sees output
  and stderr redirection works), which is why the CLI's diagnostics remain
  capturable after the print → logging migration.
"""

from __future__ import annotations

import logging

import pytest

from md2star.logging import _HANDLER_FLAG, configure, get_logger


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
    root.handlers = [h for h in saved_handlers if not getattr(h, _HANDLER_FLAG, False)]
    yield
    # Restore verbatim.
    root.handlers = saved_handlers
    root.setLevel(saved_level)
    root.propagate = saved_propagate


def _owned_handlers() -> list[logging.Handler]:
    """Return the md2star-owned handlers currently on the root logger."""
    root = logging.getLogger("md2star")
    return [h for h in root.handlers if getattr(h, _HANDLER_FLAG, False)]


def test_get_logger_is_dotted_child() -> None:
    """A module logger is namespaced under the "md2star" root."""
    assert get_logger("md2star.cli").name == "md2star.cli"
    # The default is the root name itself.
    assert get_logger().name == "md2star"


def test_configure_attaches_exactly_one_handler() -> None:
    """The first configure() installs our single stderr handler."""
    configure()
    assert len(_owned_handlers()) == 1


def test_configure_is_idempotent() -> None:
    """Repeated configure() calls must not stack duplicate handlers."""
    configure()
    configure(verbose=True)
    configure(quiet=True)
    # Still exactly one owned handler despite three calls.
    assert len(_owned_handlers()) == 1


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({}, logging.INFO),                       # default preserves old behaviour
        ({"verbose": True}, logging.DEBUG),       # --verbose shows everything
        ({"quiet": True}, logging.ERROR),         # --quiet keeps only errors
        ({"verbose": True, "quiet": True}, logging.ERROR),  # quiet wins
    ],
)
def test_configure_level_mapping(kwargs: dict[str, bool], expected: int) -> None:
    """Verbosity flags map to the documented thresholds; quiet outranks verbose."""
    configure(**kwargs)
    assert logging.getLogger("md2star").level == expected


def test_handler_follows_live_stderr(capsys) -> None:
    """A warning reaches the *current* stderr, so capsys captures it."""
    configure()
    get_logger("md2star.test").warning("hello from the logging surface")
    # capsys swapped sys.stderr after import; the live-stderr handler still
    # writes to the right place because it re-reads sys.stderr on each emit.
    assert "hello from the logging surface" in capsys.readouterr().err


def test_quiet_suppresses_warnings_but_keeps_errors(capsys) -> None:
    """--quiet hides warnings/info yet still surfaces errors."""
    configure(quiet=True)
    log = get_logger("md2star.test")
    log.warning("this warning should be hidden")
    log.error("this error must show")
    err = capsys.readouterr().err
    assert "this warning should be hidden" not in err
    assert "this error must show" in err


def test_format_is_message_only(capsys) -> None:
    """The handler prints the bare message (no level/logger prefix)."""
    configure()
    get_logger("md2star.test").error("md2star: bare message")
    # Exactly the message + newline — no "ERROR md2star.test:" decoration,
    # which is what keeps the pre-migration on-screen UX identical.
    assert capsys.readouterr().err == "md2star: bare message\n"
