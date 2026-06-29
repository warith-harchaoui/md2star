"""Unit tests for the Ollama-driven alt-text drafting pass.

The pass is gated by the same ``--lint`` flag as the LLM Markdown lint;
its safety net is identical (Ollama missing / daemon down / model not
pulled → return content unchanged). These tests mock the Ollama calls
so the suite stays hermetic — no real network, no real model.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from md2star.preprocessing.alt_text import fill_empty_alt_text


@pytest.fixture
def png_fixture(tmp_path: Path) -> Path:
    """A tiny 1×1 PNG so the pass has something to hash + base64 over."""
    from PIL import Image
    p = tmp_path / "x.png"
    Image.new("RGB", (1, 1), "white").save(p)
    return p


class TestFillEmptyAltText:
    """End-to-end behaviour of :func:`fill_empty_alt_text`."""

    def test_replaces_empty_alt_with_model_output(self, tmp_path, png_fixture):
        # Pretend the daemon is up, the model is pulled, and the request
        # returns a clean alt-text string.
        with patch(
            "md2star.preprocessing.alt_text.is_ollama_installed",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ping_ollama", return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ensure_model_pulled",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._generate_alt",
            return_value="A blank canvas",
        ):
            md = f"![]({png_fixture})\n"
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        assert f"![A blank canvas]({png_fixture})" in out

    def test_non_empty_alt_is_preserved(self, tmp_path, png_fixture):
        """An explicit alt must not be overwritten."""
        with patch(
            "md2star.preprocessing.alt_text.is_ollama_installed",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ping_ollama", return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ensure_model_pulled",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._generate_alt",
            return_value="A blank canvas",
        ) as mock_gen:
            md = f"![Already described]({png_fixture})\n"
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        assert "Already described" in out
        assert "A blank canvas" not in out
        mock_gen.assert_not_called()

    def test_missing_ollama_is_a_quiet_skip(self, tmp_path, png_fixture):
        with patch(
            "md2star.preprocessing.alt_text.is_ollama_installed",
            return_value=False,
        ):
            md = f"![]({png_fixture})"
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        assert out == md

    def test_unreachable_daemon_is_a_quiet_skip(self, tmp_path, png_fixture):
        with patch(
            "md2star.preprocessing.alt_text.is_ollama_installed",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ping_ollama", return_value=False,
        ):
            md = f"![]({png_fixture})"
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        assert out == md

    def test_remote_url_alts_are_left_alone(self, tmp_path):
        """We can't read URL-only images; the pass must skip them gracefully."""
        with patch(
            "md2star.preprocessing.alt_text.is_ollama_installed",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ping_ollama", return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ensure_model_pulled",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._generate_alt",
        ) as mock_gen:
            md = "![](https://example.invalid/foo.png)\n"
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        assert out == md
        mock_gen.assert_not_called()

    def test_response_cached_to_disk(self, tmp_path, png_fixture):
        """A second call with the same image should NOT re-query Ollama."""
        with patch(
            "md2star.preprocessing.alt_text.is_ollama_installed",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ping_ollama", return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ensure_model_pulled",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._generate_alt",
            return_value="Cached caption",
        ) as mock_gen:
            md = f"![]({png_fixture})\n"
            _ = fill_empty_alt_text(md, base_dir=str(tmp_path))
            _ = fill_empty_alt_text(md, base_dir=str(tmp_path))
            assert mock_gen.call_count == 1, (
                "second call should hit the cache, not the network"
            )

    def test_code_fence_contents_untouched(self, tmp_path, png_fixture):
        """An ``![]()`` *inside* a code block is example syntax, not a real image."""
        with patch(
            "md2star.preprocessing.alt_text.is_ollama_installed",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ping_ollama", return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ensure_model_pulled",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._generate_alt",
            return_value="Should not appear",
        ) as mock_gen:
            md = f"```\n![]({png_fixture})\n```\n"
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        assert out == md
        mock_gen.assert_not_called()

    def test_alt_with_closing_bracket_is_escaped(self, tmp_path, png_fixture):
        """A model that emits ``]`` must not break the Markdown image syntax."""
        with patch(
            "md2star.preprocessing.alt_text.is_ollama_installed",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ping_ollama", return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._ensure_model_pulled",
            return_value=True,
        ), patch(
            "md2star.preprocessing.alt_text._generate_alt",
            return_value="A [tricky] caption",
        ):
            md = f"![]({png_fixture})"
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        # ``]`` inside the alt must be escaped so the closing of the
        # image ref still wins parsing.
        assert "\\]" in out
        assert f"({png_fixture})" in out


class TestModelOverride:
    """``MD2STAR_ALT_TEXT_MODEL`` env override is honoured."""

    def test_default_falls_back_to_lint_model(self, monkeypatch):
        """Without an override, alt-text mirrors the text lint model so one
        ``ollama pull`` powers both passes (gemma4:e2b is multimodal).
        """
        monkeypatch.delenv("MD2STAR_ALT_TEXT_MODEL", raising=False)
        monkeypatch.delenv("MD2STAR_LINT_MODEL", raising=False)
        from md2star.preprocessing.alt_text import _default_alt_text_model
        from md2star.preprocessing.lint import _default_lint_model
        assert _default_alt_text_model() == _default_lint_model()
        assert _default_alt_text_model().startswith("gemma4:")

    def test_env_override_wins(self, monkeypatch):
        monkeypatch.setenv("MD2STAR_ALT_TEXT_MODEL", "moondream:v2")
        from md2star.preprocessing.alt_text import _default_alt_text_model
        assert _default_alt_text_model() == "moondream:v2"

    def test_lint_env_propagates_to_alt_text(self, monkeypatch):
        """If the user overrode the lint model, alt-text follows it."""
        monkeypatch.delenv("MD2STAR_ALT_TEXT_MODEL", raising=False)
        monkeypatch.setenv("MD2STAR_LINT_MODEL", "qwen2.5-vl:7b")
        from md2star.preprocessing.alt_text import _default_alt_text_model
        assert _default_alt_text_model() == "qwen2.5-vl:7b"
