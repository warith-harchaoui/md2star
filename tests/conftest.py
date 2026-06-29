"""Test-suite fixtures.

The autouse ``isolated_cache`` fixture redirects ``$MD2STAR_CACHE_DIR`` to a
fresh ``tmp_path`` for every test, so cache artifacts (resized rasters,
SVG→PNG conversions, downloaded remote images, mermaid renders) land in a
known location and do not pollute the user's real cache.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    """Force every test to use a private cache dir under tmp_path."""
    cache_root = tmp_path / "md2star-cache"
    monkeypatch.setenv("MD2STAR_CACHE_DIR", str(cache_root))
    return cache_root
