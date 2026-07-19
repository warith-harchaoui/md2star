"""Unit tests for the Ollama-driven alt-text drafting pass.

Gated by the same ``--lint`` flag as the LLM Markdown lint; its safety net is
identical (Ollama missing / daemon down / model not pulled → content unchanged).
The Ollama calls are mocked so the suite stays hermetic. Three functional tests
cover the whole surface: the rewrite decision + edge behaviours (caching,
``]``-escaping), the broken-environment quiet-skip contract, and model-override
precedence.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from md2star.preprocessing.alt_text import fill_empty_alt_text

_MOD = "md2star.preprocessing.alt_text"


@pytest.fixture
def png_fixture(tmp_path: Path) -> Path:
    """Write a tiny 1×1 PNG the pass can hash + base64."""
    from PIL import Image
    p = tmp_path / "x.png"
    Image.new("RGB", (1, 1), "white").save(p)
    return p


@contextmanager
def _ollama_up(gen_return: str = "A blank canvas"):
    """Patch the whole Ollama stack to a healthy daemon returning *gen_return*.

    Yields the ``_generate_alt`` mock for call-count / not-called assertions.
    """
    with patch(f"{_MOD}.is_ollama_installed", return_value=True), \
         patch(f"{_MOD}._ping_ollama", return_value=True), \
         patch(f"{_MOD}._ensure_model_pulled", return_value=True), \
         patch(f"{_MOD}._generate_alt", return_value=gen_return) as gen:
        yield gen


def test_rewrite_decision_and_edge_behaviours(tmp_path, png_fixture) -> None:
    """The pass rewrites only readable, out-of-fence, empty-alt images — plus caching + escaping.

    Sweeps every "should this image be rewritten?" case, then folds in the two
    edge behaviours that don't fit an in/out table: the per-image disk cache and
    the ``]``-escaping of a model caption.
    """
    # Rewrite matrix: only an empty-alt readable local image is rewritten.
    cases = [
        ("![]({img})\n", True, "empty alt on a readable local image"),
        ("![Already described]({img})\n", False, "non-empty alt is preserved"),
        ("![](https://example.invalid/foo.png)\n", False, "remote url is unreadable"),
        ("```\n![]({img})\n```\n", False, "code-fence content is untouched"),
    ]
    for template, should_rewrite, reason in cases:
        md = template.format(img=png_fixture)
        with _ollama_up("A blank canvas") as gen:
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        if should_rewrite:
            assert f"![A blank canvas]({png_fixture})" in out, reason
        else:
            assert out == md, reason
            gen.assert_not_called()

    # Disk cache is keyed by image content, so the caching + escaping checks use
    # fresh distinct images (different bytes → different hash) to avoid reusing
    # the caption cached for png_fixture above.
    from PIL import Image
    img2 = tmp_path / "red.png"
    Image.new("RGB", (1, 1), "red").save(img2)
    img3 = tmp_path / "blue.png"
    Image.new("RGB", (1, 1), "blue").save(img3)

    # Disk cache: a repeat call with the same image reaches the model only once.
    md = f"![]({img2})\n"
    with _ollama_up("Cached caption") as gen:
        fill_empty_alt_text(md, base_dir=str(tmp_path))
        fill_empty_alt_text(md, base_dir=str(tmp_path))
        assert gen.call_count == 1, "second call should hit the cache, not the network"

    # A model-emitted ``]`` is escaped so the image ref still parses, path intact.
    with _ollama_up("A [tricky] caption"):
        out = fill_empty_alt_text(f"![]({img3})", base_dir=str(tmp_path))
    assert "\\]" in out and f"({img3})" in out


def test_broken_environment_is_a_quiet_skip(tmp_path, png_fixture) -> None:
    """A missing binary or an unreachable daemon returns the content unchanged."""
    md = f"![]({png_fixture})"
    for installed, reachable, reason in [
        (False, True, "binary not on PATH"),
        (True, False, "daemon unreachable"),
    ]:
        with patch(f"{_MOD}.is_ollama_installed", return_value=installed), \
             patch(f"{_MOD}._ping_ollama", return_value=reachable):
            assert fill_empty_alt_text(md, base_dir=str(tmp_path)) == md, reason


def test_model_resolution_precedence(monkeypatch) -> None:
    """Alt-text model = alt override → lint override → shared gemma4 default."""
    from md2star.preprocessing.alt_text import _default_alt_text_model
    from md2star.preprocessing.lint import _default_lint_model

    for alt_env, lint_env, expected in [
        (None, None, "__lint_default__"),       # defaults coincide (gemma4)
        ("moondream:v2", None, "moondream:v2"),  # alt override wins
        (None, "qwen2.5-vl:7b", "qwen2.5-vl:7b"),  # inherits the lint override
    ]:
        for name, val in (("MD2STAR_ALT_TEXT_MODEL", alt_env), ("MD2STAR_LINT_MODEL", lint_env)):
            if val is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, val)
        resolved = _default_alt_text_model()
        if expected == "__lint_default__":
            assert resolved == _default_lint_model() and resolved.startswith("gemma4:")
        else:
            assert resolved == expected
