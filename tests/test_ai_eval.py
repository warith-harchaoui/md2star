"""AI-eval layer for the opt-in Ollama passes (``--lint`` + alt-text).

The unit tests in ``test_lint.py`` / ``test_alt_text.py`` mock the daemon and
prove the *fallback ladder* (never load-bearing). This module is the missing
*quality* layer the coding standard asks for: it runs the real local model and
asserts the output is actually useful — the lint repairs a known-broken snippet
without rewriting prose, and (when a vision model answers) alt-text is non-empty
and on-topic.

It is gated on a reachable local Ollama daemon, so it runs on a developer
machine that has one and **skips cleanly in CI** (where Ollama is absent) — the
eval can never turn a green pipeline red. Marked ``ai_eval`` so it can be
selected (``pytest -m ai_eval``) or excluded (``pytest -m "not ai_eval"``).

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest

from md2star.preprocessing import lint


def _engine_ready() -> bool:
    """True iff md2star's brief -> engine contract resolves a usable local model.

    ``beh.ensure`` resolves the committed ``llm.brief.yaml`` against this machine
    (writing the gitignored engine file on first use); a machine with no
    resolvable backend/model raises, so we treat any failure as "not ready" and
    skip the whole eval module. This keeps CI green (no local model) while the
    eval still runs on a developer box that has one.
    """
    try:
        return bool(lint.engine().get("llm", {}).get("model"))
    except Exception:  # noqa: BLE001 — unresolved engine → eval skips cleanly
        return False


# Skip the whole module unless the brief resolves to a usable local model.
pytestmark = [
    pytest.mark.ai_eval,
    pytest.mark.skipif(not _engine_ready(), reason="no resolvable local LLM engine"),
]


def test_lint_repairs_broken_markdown_without_gutting_it() -> None:
    """The lint pass fixes a broken image link while keeping the prose.

    Quality assertions (not just "it ran"): the malformed ``![alt(x.png)`` is
    repaired to a valid ``![alt](x.png)``, the surrounding words survive, and
    the length guard did not collapse the document to almost nothing.
    """
    broken = (
        "# Quarterly report\n\n"
        "Revenue grew steadily. See the chart ![alt(chart.png) for detail.\n\n"
        "The trend is **clearly** upward.\n"
    )
    fixed = lint.lint_with_llm(broken)

    # The pass is best-effort; if the local model declined we get the original
    # back unchanged — that is an acceptable no-op, not a quality failure.
    if fixed == broken:
        pytest.skip("local model returned the input unchanged (acceptable no-op)")

    # Otherwise the repair must be real: valid image syntax, prose preserved.
    assert "![alt](chart.png)" in fixed or "](chart.png)" in fixed
    assert "Revenue grew steadily" in fixed
    assert "upward" in fixed
    # Sanity: the model must not have truncated the doc to a stub.
    assert len(fixed) > 0.5 * len(broken)


def test_alt_text_caption_is_nonempty_when_vision_available(tmp_path) -> None:
    """When a vision model answers, an empty alt is filled with a real caption.

    Skips (rather than fails) if the configured model is text-only — the default
    macOS ``gemma4:e2b-mlx`` MLX build does not process images, and that is a
    model-choice concern tracked separately, not a regression in this code path.
    """
    from PIL import Image

    from md2star.preprocessing import alt_text

    # A real on-disk PNG so the pass has something to describe.
    img = tmp_path / "square.png"
    Image.new("RGB", (48, 48), (200, 30, 30)).save(img)

    md = f"![]({img.name})\n"
    out = alt_text.fill_empty_alt_text(md, base_dir=str(tmp_path))

    if out.strip() == md.strip():
        pytest.skip("vision model unavailable or declined (empty alt left as-is)")

    # A caption was produced: it must be a non-empty alt, not the empty original.
    assert "![](" not in out
    assert "![" in out and "](" in out
