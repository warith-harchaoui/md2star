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


def test_run_surfaces_a_neutral_draft_summary(tmp_path, png_fixture, caplog) -> None:
    """After drafting, an INFO summary lists each image → its alt text (seamless FYI).

    The drafting stays seamless (nothing to approve), but the run is never silent:
    a neutral summary at INFO surfaces exactly what went in, so ``--quiet`` hides
    it while a default run shows it.
    """
    import logging

    md = f"Intro prose about the picture below.\n\n![]({png_fixture})\n"
    with _ollama_up("A blank canvas"), caplog.at_level(logging.INFO, logger="md2star"):
        fill_empty_alt_text(md, base_dir=str(tmp_path))

    assert "drafted alt text" in caplog.text
    assert "A blank canvas" in caplog.text
    assert str(png_fixture) in caplog.text


def test_prompt_uses_detected_language_and_surrounding_context(tmp_path, png_fixture) -> None:
    """The per-image prompt is written in the document's detected language and
    carries the surrounding text as context.

    A French document must yield a "…in French" instruction (auto-detected, not a
    hardcoded EN/FR toggle) and fold the nearest heading + prose into the prompt,
    so the model describes the image in place. We capture the prompt handed to
    ``_generate_alt`` to assert both.
    """
    captured: dict[str, str] = {}

    def _capture(image_path, model, prompt, timeout=60.0):
        captured["prompt"] = prompt
        return "Un vélo rouge"

    md = (
        "# Rapport trimestriel d'ingénierie\n\n"
        "Le graphique ci-dessous montre clairement que la latence du service "
        "a fortement diminué au cours du dernier trimestre grâce aux nouvelles "
        "optimisations déployées par l'équipe.\n\n"
        f"![]({png_fixture})\n"
    )
    mod = "md2star.preprocessing.alt_text"
    with patch(f"{mod}.is_ollama_installed", return_value=True), \
         patch(f"{mod}._ping_ollama", return_value=True), \
         patch(f"{mod}._ensure_model_pulled", return_value=True), \
         patch(f"{mod}._generate_alt", side_effect=_capture):
        out = fill_empty_alt_text(md, base_dir=str(tmp_path))

    prompt = captured["prompt"]
    # Language auto-detected from the French body → the instruction names French.
    assert "in French" in prompt
    # Surrounding context (heading + nearby prose) is folded into the prompt.
    assert "Rapport trimestriel" in prompt or "latence" in prompt
    # The generated caption lands in the alt slot.
    assert "![Un vélo rouge]" in out


def test_model_resolution_precedence(monkeypatch) -> None:
    """Alt-text model = MD2STAR_ALT_TEXT_MODEL override, else the suite LLM default.

    The default vision model is single-sourced from the suite config via
    ``osh.llm_model()`` (multimodal, e.g. ``qwen2.5vl:7b``) — not hard-coded here,
    so bumping the suite model does not break this test. An explicit
    ``MD2STAR_ALT_TEXT_MODEL`` still wins, and ``MD2STAR_LINT_MODEL`` (text lint)
    must never influence the alt-text model.
    """
    import os_helper as osh

    from md2star.preprocessing.alt_text import _DEFAULT_ALT_MODEL, _default_alt_text_model

    assert _DEFAULT_ALT_MODEL == osh.llm_model()
    for alt_env, expected in [
        (None, _DEFAULT_ALT_MODEL),          # no override → the vision default
        ("moondream:v2", "moondream:v2"),    # explicit override wins
    ]:
        if alt_env is None:
            monkeypatch.delenv("MD2STAR_ALT_TEXT_MODEL", raising=False)
        else:
            monkeypatch.setenv("MD2STAR_ALT_TEXT_MODEL", alt_env)
        # The lint model env var must NOT influence the alt-text model anymore.
        monkeypatch.setenv("MD2STAR_LINT_MODEL", "qwen2.5-vl:7b")
        assert _default_alt_text_model() == expected
