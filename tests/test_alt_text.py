"""Unit tests for the Ollama-driven alt-text drafting pass.

The pass is gated by the same ``--lint`` flag as the LLM Markdown lint;
its safety net is identical (Ollama missing / daemon down / model not
pulled → return content unchanged). These tests mock the Ollama calls
so the suite stays hermetic — no real network, no real model.

The suite is organised around distinct *behaviours* rather than one
test per input variant:

* :class:`TestFillEmptyAltText` drives the pass end to end. A single
  parametrised test sweeps every "should this image be rewritten?"
  decision (empty vs. filled alt, local vs. remote, in-fence vs. real),
  and standalone tests cover the two edge behaviours — disk caching and
  ``]`` escaping — that don't fit a simple in/out table.
* :class:`TestSafetyNet` folds the "quiet skip" contract (missing binary
  / unreachable daemon) into one parametrised test.
* :class:`TestModelOverride` keeps the env-precedence cases together.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from md2star.preprocessing.alt_text import fill_empty_alt_text


@pytest.fixture
def png_fixture(tmp_path: Path) -> Path:
    """Write a tiny 1×1 PNG the pass can hash + base64.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest per-test temporary directory.

    Returns
    -------
    pathlib.Path
        Path to the freshly written PNG.
    """
    from PIL import Image
    p = tmp_path / "x.png"
    Image.new("RGB", (1, 1), "white").save(p)
    return p


@contextmanager
def _ollama_up(gen_return: str = "A blank canvas"):
    """Patch the whole Ollama stack to a healthy, deterministic daemon.

    Every gating helper reports success and ``_generate_alt`` returns a
    fixed caption, so the pass exercises its rewrite path without touching
    the network. Used as ``with _ollama_up() as gen:``; the yielded value
    is the ``_generate_alt`` mock, for call-count / not-called assertions.

    Parameters
    ----------
    gen_return : str, optional
        Caption the mocked model returns for every image.

    Yields
    ------
    unittest.mock.MagicMock
        The patched ``_generate_alt`` mock.
    """
    mod = "md2star.preprocessing.alt_text"
    # The daemon is installed, reachable, and the model is pulled; the
    # generation call returns a fixed caption, and its mock is yielded.
    with patch(f"{mod}.is_ollama_installed", return_value=True), patch(
        f"{mod}._ping_ollama", return_value=True,
    ), patch(
        f"{mod}._ensure_model_pulled", return_value=True,
    ), patch(
        f"{mod}._generate_alt", return_value=gen_return,
    ) as gen:
        yield gen


class TestFillEmptyAltText:
    """End-to-end behaviour of :func:`fill_empty_alt_text`."""

    @pytest.mark.parametrize(
        "template, should_rewrite, reason",
        [
            # An empty-alt local image is the one case we DO rewrite.
            ("![]({img})\n", True, "empty alt on a readable local image"),
            # An explicit alt must never be overwritten.
            ("![Already described]({img})\n", False, "non-empty alt is preserved"),
            # URL-only images can't be read from disk, so skip them.
            ("![](https://example.invalid/foo.png)\n", False, "remote url is unreadable"),
            # ``![]()`` inside a fence is example syntax, not a real image.
            ("```\n![]({img})\n```\n", False, "code-fence content is untouched"),
        ],
    )
    def test_rewrite_decision(self, tmp_path, png_fixture, template, should_rewrite, reason):
        """The pass rewrites only readable, out-of-fence, empty-alt images.

        Parameters
        ----------
        tmp_path : pathlib.Path
            Per-test temp dir used as ``base_dir``.
        png_fixture : pathlib.Path
            A real PNG substituted into ``{img}`` templates.
        template : str
            Markdown template; ``{img}`` (if present) is filled with the PNG.
        should_rewrite : bool
            Whether this input should have its alt replaced.
        reason : str
            Human-readable rationale surfaced in assertion messages.
        """
        md = template.format(img=png_fixture)
        with _ollama_up("A blank canvas") as gen:
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        if should_rewrite:
            # The model caption lands inside the alt slot.
            assert f"![A blank canvas]({png_fixture})" in out, reason
        else:
            # Nothing changed and the model was never consulted.
            assert out == md, reason
            gen.assert_not_called()

    def test_response_cached_to_disk(self, tmp_path, png_fixture):
        """A repeat call with the same image hits the disk cache, not the model.

        Parameters
        ----------
        tmp_path : pathlib.Path
            Per-test temp dir used as ``base_dir`` and cache root.
        png_fixture : pathlib.Path
            The image whose caption should be memoised.
        """
        md = f"![]({png_fixture})\n"
        with _ollama_up("Cached caption") as gen:
            _ = fill_empty_alt_text(md, base_dir=str(tmp_path))
            _ = fill_empty_alt_text(md, base_dir=str(tmp_path))
            # Only the first pass reaches _generate_alt; the second is cached.
            assert gen.call_count == 1, "second call should hit the cache, not the network"

    def test_alt_with_closing_bracket_is_escaped(self, tmp_path, png_fixture):
        """A model-emitted ``]`` is escaped so the image syntax still parses.

        Parameters
        ----------
        tmp_path : pathlib.Path
            Per-test temp dir used as ``base_dir``.
        png_fixture : pathlib.Path
            The image whose (tricky) caption is generated.
        """
        md = f"![]({png_fixture})"
        with _ollama_up("A [tricky] caption"):
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        # ``]`` inside the alt is escaped so the closing of the image ref
        # still wins parsing, and the target path is left intact.
        assert "\\]" in out
        assert f"({png_fixture})" in out


class TestSafetyNet:
    """A broken Ollama environment degrades to a silent no-op."""

    @pytest.mark.parametrize(
        "installed, reachable, reason",
        [
            (False, True, "binary not on PATH"),
            (True, False, "daemon unreachable"),
        ],
    )
    def test_broken_environment_is_a_quiet_skip(self, tmp_path, png_fixture, installed, reachable, reason):
        """Missing binary or dead daemon returns the content unchanged.

        Parameters
        ----------
        tmp_path : pathlib.Path
            Per-test temp dir used as ``base_dir``.
        png_fixture : pathlib.Path
            A readable local image that would otherwise be rewritten.
        installed : bool
            Simulated ``is_ollama_installed`` result.
        reachable : bool
            Simulated ``_ping_ollama`` result.
        reason : str
            Rationale surfaced in the assertion message.
        """
        mod = "md2star.preprocessing.alt_text"
        md = f"![]({png_fixture})"
        with patch(f"{mod}.is_ollama_installed", return_value=installed), patch(
            f"{mod}._ping_ollama", return_value=reachable,
        ):
            out = fill_empty_alt_text(md, base_dir=str(tmp_path))
        # A skip is transparent: the exact input comes back out.
        assert out == md, reason


class TestModelOverride:
    """``MD2STAR_ALT_TEXT_MODEL`` / ``MD2STAR_LINT_MODEL`` precedence."""

    @pytest.mark.parametrize(
        "alt_env, lint_env, expected",
        [
            # No overrides: alt-text mirrors the lint default (a gemma4 model),
            # so one ``ollama pull`` powers both passes (gemma4:e2b is multimodal).
            (None, None, "__lint_default__"),
            # A dedicated alt-text override beats everything.
            ("moondream:v2", None, "moondream:v2"),
            # With only the lint model set, alt-text inherits the user's choice.
            (None, "qwen2.5-vl:7b", "qwen2.5-vl:7b"),
        ],
    )
    def test_model_resolution_precedence(self, monkeypatch, alt_env, lint_env, expected):
        """Alt-text model = override → lint override → shared gemma4 default.

        Parameters
        ----------
        monkeypatch : pytest.MonkeyPatch
            Sets or clears the two model env vars per case.
        alt_env : str or None
            Value for ``MD2STAR_ALT_TEXT_MODEL`` (``None`` clears it).
        lint_env : str or None
            Value for ``MD2STAR_LINT_MODEL`` (``None`` clears it).
        expected : str
            Expected resolved model, or the sentinel ``"__lint_default__"``
            meaning "must equal the lint default (a gemma4 model)".
        """
        # Apply each env var, deleting when the case wants it unset.
        for name, val in (("MD2STAR_ALT_TEXT_MODEL", alt_env), ("MD2STAR_LINT_MODEL", lint_env)):
            if val is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, val)

        from md2star.preprocessing.alt_text import _default_alt_text_model
        resolved = _default_alt_text_model()
        if expected == "__lint_default__":
            # Defaults coincide, and the shared default is a gemma4 model.
            from md2star.preprocessing.lint import _default_lint_model
            assert resolved == _default_lint_model()
            assert resolved.startswith("gemma4:")
        else:
            # An override (alt-text or lint) is honoured verbatim.
            assert resolved == expected
