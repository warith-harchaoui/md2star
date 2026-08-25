"""Unit tests for the LLM-driven alt-text drafting pass.

Gated by the same ``--lint`` flag as the LLM Markdown lint; its safety net is
identical (any model-call failure → the affected image is left unchanged). The
model call (:func:`_generate_alt`, which reads the image to bytes and calls
``best_engine_ai_helper.llm.chat``) is mocked so the suite stays hermetic, and
``alt_text.engine`` is stubbed so no real brief -> engine resolution runs. Three
functional tests cover the whole surface: the rewrite decision + edge behaviours
(caching, ``]``-escaping), the failure quiet-skip contract, and the cache-key
model-tag precedence.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest

from md2star.preprocessing import alt_text
from md2star.preprocessing.alt_text import fill_empty_alt_text

_MOD = "md2star.preprocessing.alt_text"

# A stand-in engine descriptor; the concrete shape only matters for the cache-key
# vlm tag (``_alt_model_tag``). llm.chat is mocked, so nothing else reads it.
_FAKE_ENGINE = {"backend": "ollama", "base_url": None, "vlm": {"model": "fake-vlm:2b"}}


@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch) -> None:
    """Pin ``alt_text.engine`` to a fake so no real engine resolution happens."""
    monkeypatch.setattr(alt_text, "engine", lambda: _FAKE_ENGINE)


@pytest.fixture
def png_fixture(tmp_path: Path) -> Path:
    """Write a tiny 1×1 PNG the pass can hash + read."""
    from PIL import Image

    p = tmp_path / "x.png"
    Image.new("RGB", (1, 1), "white").save(p)
    return p


@contextmanager
def _model_returns(caption: str = "A blank canvas"):
    """Patch ``_generate_alt`` to a model that returns *caption*.

    Yields the ``_generate_alt`` mock for call-count / not-called assertions.
    """
    with patch(f"{_MOD}._generate_alt", return_value=caption) as gen:
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
        with _model_returns("A blank canvas") as gen:
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
    with _model_returns("Cached caption") as gen:
        fill_empty_alt_text(md, base_dir=str(tmp_path))
        fill_empty_alt_text(md, base_dir=str(tmp_path))
        assert gen.call_count == 1, "second call should hit the cache, not the network"

    # A model-emitted ``]`` is escaped so the image ref still parses, path intact.
    with _model_returns("A [tricky] caption"):
        out = fill_empty_alt_text(f"![]({img3})", base_dir=str(tmp_path))
    assert "\\]" in out and f"({img3})" in out


def test_model_failure_is_a_quiet_skip(tmp_path, png_fixture) -> None:
    """When the model call fails (returns ``None``), the image is left unchanged."""
    md = f"![]({png_fixture})"
    with patch(f"{_MOD}._generate_alt", return_value=None):
        assert fill_empty_alt_text(md, base_dir=str(tmp_path)) == md


def test_run_surfaces_a_neutral_draft_summary(tmp_path, png_fixture, caplog) -> None:
    """After drafting, an INFO summary lists each image → its alt text (seamless FYI).

    The drafting stays seamless (nothing to approve), but the run is never silent:
    a neutral summary at INFO surfaces exactly what went in, so ``--quiet`` hides
    it while a default run shows it.
    """
    import logging

    md = f"Intro prose about the picture below.\n\n![]({png_fixture})\n"
    with _model_returns("A blank canvas"), caplog.at_level(logging.INFO, logger="md2star"):
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
    with patch(f"{_MOD}._generate_alt", side_effect=_capture):
        out = fill_empty_alt_text(md, base_dir=str(tmp_path))

    prompt = captured["prompt"]
    # Language auto-detected from the French body → the instruction names French.
    assert "in French" in prompt
    # Surrounding context (heading + nearby prose) is folded into the prompt.
    assert "Rapport trimestriel" in prompt or "latence" in prompt
    # The generated caption lands in the alt slot.
    assert "![Un vélo rouge]" in out


def test_cache_key_model_tag_precedence(monkeypatch) -> None:
    """Cache-key tag = explicit override, else the resolved engine's vlm model.

    The concrete model is owned by the engine descriptor, not this module. When a
    caller passes an explicit tag it wins; otherwise the tag is read from the
    engine's ``vlm`` section (here the stubbed ``fake-vlm:2b``). A resolution
    failure degrades to the stable ``"vlm"`` key.
    """
    assert alt_text._alt_model_tag(None) == "fake-vlm:2b"
    assert alt_text._alt_model_tag("override:1b") == "override:1b"

    # Engine that cannot resolve → the coarse-but-stable fallback key.
    def _boom():
        raise RuntimeError("no brief")

    monkeypatch.setattr(alt_text, "engine", _boom)
    assert alt_text._alt_model_tag(None) == "vlm"
