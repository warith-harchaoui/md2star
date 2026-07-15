"""Functional tests for the XDG-style cache resolver (``md2star.cache``).

These cover the two things the cache module promises: the ``cache_dir`` /
``clear_cache`` contract callers rely on (create-on-demand, honor the
``MD2STAR_CACHE_DIR`` override, report bytes freed), and the per-OS root
resolution in ``_platform_cache_root`` — which is pure branch logic over
``sys.platform`` + a couple of environment variables, so it is exercised here
by monkeypatching those boundaries rather than by running on three machines.

The autouse fixture in ``conftest.py`` points ``MD2STAR_CACHE_DIR`` at a
tmp dir for every test; the platform-root cases below explicitly drop that
override (and ``XDG_CACHE_HOME``) so they see the real resolution path.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

from pathlib import Path

import pytest

from md2star import cache


def test_cache_dir_override_and_subdir(tmp_path, monkeypatch) -> None:
    """``MD2STAR_CACHE_DIR`` replaces the root; subdirs are created eagerly.

    The override is the escape hatch tests and CI use to keep runs off the
    real user cache, so it must win over the computed platform root and
    create both the root and any requested subdirectory on first call.
    """
    # Point the cache at a fresh tmp root via the documented override.
    root = tmp_path / "cache-root"
    monkeypatch.setenv("MD2STAR_CACHE_DIR", str(root))

    # Bare call returns the override root and has already created it.
    got = cache.cache_dir()
    assert got == root
    assert got.is_dir()

    # A subdir request returns root/<subdir>, also created on the spot.
    sub = cache.cache_dir("remote")
    assert sub == root / "remote"
    assert sub.is_dir()


def test_clear_cache_reports_bytes_and_removes(tmp_path, monkeypatch) -> None:
    """``clear_cache`` tallies the bytes it frees and deletes the tree.

    The byte count is what the ``md2star clear-cache`` CLI reports back, so it
    must equal the on-disk payload; afterwards the directory must be gone.
    """
    root = tmp_path / "cache-clear"
    monkeypatch.setenv("MD2STAR_CACHE_DIR", str(root))

    # Seed two files across a subdir so the walk has something to tally.
    cache.cache_dir("a").joinpath("f1.bin").write_bytes(b"x" * 100)
    cache.cache_dir("b").joinpath("f2.bin").write_bytes(b"y" * 50)

    freed = cache.clear_cache()

    # The reported total matches exactly the bytes we wrote (100 + 50) …
    assert freed == 150
    # … and the whole cache root is removed (clear_cache does not recreate it).
    assert not root.exists()


# Each row is (platform, env-overrides, expected-suffix-relative-to-home-or-abs).
# `home` is a sentinel replaced with the monkeypatched home dir; an absolute
# Path means the value should be returned verbatim regardless of home.
@pytest.mark.parametrize(
    ("platform", "env", "expected_parts"),
    [
        # XDG_CACHE_HOME wins on every platform when set.
        ("linux", {"XDG_CACHE_HOME": "/xdg/cache"}, "/xdg/cache"),
        ("darwin", {"XDG_CACHE_HOME": "/xdg/cache"}, "/xdg/cache"),
        # macOS default: ~/Library/Caches.
        ("darwin", {}, ("Library", "Caches")),
        # Windows with LOCALAPPDATA set uses it verbatim.
        ("win32", {"LOCALAPPDATA": "/win/local"}, "/win/local"),
        # Windows without LOCALAPPDATA falls back to ~/AppData/Local.
        ("win32", {}, ("AppData", "Local")),
        # Linux/BSD default when XDG is unset: ~/.cache.
        ("linux", {}, (".cache",)),
    ],
)
def test_platform_cache_root(tmp_path, monkeypatch, platform, env, expected_parts) -> None:
    """``_platform_cache_root`` honors XDG first, then per-OS conventions.

    Parameters
    ----------
    platform : str
        Value patched onto ``sys.platform`` for the case.
    env : dict
        Environment overrides to set (others are cleared).
    expected_parts : str or tuple
        An absolute path expected verbatim, or a tuple of trailing path
        components expected under the (patched) home directory.
    """
    # Neutralize the boundaries: fake home, chosen platform, and a clean env
    # so only the case's own variables influence the branch taken.
    fake_home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setattr(cache.sys, "platform", platform)
    monkeypatch.delenv("MD2STAR_CACHE_DIR", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    root = cache._platform_cache_root()

    # Absolute-path expectations must match verbatim; component tuples are
    # resolved relative to the patched home dir.
    if isinstance(expected_parts, str):
        assert root == Path(expected_parts)
    else:
        assert root == fake_home.joinpath(*expected_parts)
