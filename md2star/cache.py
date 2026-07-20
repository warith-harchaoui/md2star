"""Per-user cache directory for md2star image/mermaid artifacts.

Module summary
--------------
Historically, downscaled images, downloaded remote images, and rendered
mermaid PNGs all landed next to the user's source Markdown, cluttering
working directories with hidden dotfiles (``.remote_*``, ``*_max1600.*``,
``*_cell.*``, ``.mermaid_*``). This module centralises every artifact under
``$XDG_CACHE_HOME/md2star/`` (with platform fallbacks) so the user's source
trees stay clean and the cache can be wiped with a single
``md2star clear-cache``.

Cache layout::

    $XDG_CACHE_HOME/md2star/
    ├── remote/           # downloaded http(s):// images, keyed by URL MD5
    ├── resized/          # downscaled rasters, keyed by source-path + size MD5
    ├── cell/             # cell-fitted images, keyed by source-path MD5
    └── mermaid/          # rendered mermaid PNGs + resolved config JSON

The hash-keyed filenames make collisions across users impossible — two
different source files with the same basename do not stomp each other.

Usage
-----
>>> from md2star.cache import cache_dir, clear_cache
>>> p = cache_dir("remote")
>>> print(p.name)  # 'remote'
remote
>>> freed = clear_cache()
>>> print(freed >= 0)  # True
True

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import os_helper as osh

_APP_NAME = "md2star"


def _platform_cache_root() -> Path:
    """Return the per-user cache root using each platform's convention.

    * Linux/BSD: ``$XDG_CACHE_HOME`` (default ``~/.cache``).
    * macOS: ``~/Library/Caches`` (Apple's documented per-user cache dir).
    * Windows: ``%LOCALAPPDATA%`` (default ``~\\AppData\\Local``).
    """
    # XDG_CACHE_HOME wins on every platform when set: it's the explicit
    # user/CI override and the freedesktop standard, so we honour it before
    # falling back to OS-specific defaults.
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg)

    # macOS keeps per-user caches under ~/Library/Caches (Apple convention);
    # putting them in ~/.cache would work but violates platform expectations.
    # os_helper.macos()/windows() centralise the OS check for the whole suite.
    if osh.macos():
        return Path.home() / "Library" / "Caches"
    # Windows: %LOCALAPPDATA% is the roaming-excluded per-user store. Fall
    # back to its documented default only if the env var is somehow unset.
    if osh.windows():
        local = os.environ.get("LOCALAPPDATA")
        if local:
            return Path(local)
        return Path.home() / "AppData" / "Local"
    # Linux/BSD default when XDG_CACHE_HOME is unset.
    return Path.home() / ".cache"


def cache_dir(subdir: str | None = None) -> Path:
    """Return the md2star cache dir (or a subdirectory of it), creating it.

    Honors ``MD2STAR_CACHE_DIR`` for testing / opt-out (e.g. a tempdir in CI).
    """
    # MD2STAR_CACHE_DIR fully replaces the computed root — tests point it at a
    # tmpdir so a run never touches the real user cache.
    override = os.environ.get("MD2STAR_CACHE_DIR")
    root = Path(override) if override else (_platform_cache_root() / _APP_NAME)
    target = root / subdir if subdir else root
    # Create eagerly (parents + idempotent) so callers can write immediately
    # without each having to guard existence — os_helper.make_directory wraps
    # the mkdir(parents=True, exist_ok=True) idiom for the whole suite.
    osh.make_directory(str(target))
    return target


def clear_cache() -> int:
    """Remove the entire md2star cache directory. Returns bytes freed (approx)."""
    root = cache_dir()
    # Tally sizes BEFORE deleting so we can report how much was freed. We walk
    # rather than stat the dir because a directory's own size isn't its
    # contents' total on most filesystems.
    total = 0
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                # A file vanishing mid-walk (races, broken symlink) shouldn't
                # abort the tally — skip it and keep counting.
                pass
    # ignore_errors: a partial cache (permission quirks, open handles) should
    # still clear as much as possible rather than raise.
    shutil.rmtree(root, ignore_errors=True)
    return total
