"""Functional tests for the opt-in LLM lint pass (``md2star.preprocessing.lint``).

The pass routes every model call through ``best_engine_ai_helper.llm.chat``,
reading the backend + model from md2star's resolved engine descriptor. The unit
tests mock both seams — ``lint.engine`` (so no real brief -> engine resolution
happens) and ``lint.llm.chat`` (so no daemon is contacted) — and prove the
contract that lint is **never load-bearing**: whatever goes wrong (engine cannot
resolve, transport error, empty/oversized output), the original Markdown is
returned unchanged.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest

from md2star.preprocessing import lint

# A stand-in engine descriptor; the real shape is irrelevant because llm.chat is
# mocked — lint only forwards it.
_FAKE_ENGINE = {"backend": "ollama", "base_url": None, "llm": {"model": "fake:1b"}}


@pytest.fixture(autouse=True)
def _stub_engine(monkeypatch) -> None:
    """Pin ``lint.engine`` to a fake so no real brief -> engine resolution runs."""
    monkeypatch.setattr(lint, "engine", lambda: _FAKE_ENGINE)


def test_lint_applies_only_a_sane_fix(monkeypatch) -> None:
    """The model's fix is applied only when it is non-empty and a sane length.

    Walks the whole ladder — transport error, empty output, length-guard trip,
    and the happy path — asserting the input is returned verbatim except when
    the model returns sane output.
    """
    content = "# Title\n\nSome body text that is long enough to compare."
    fixed_text = "# Title\n\nSome body text that is long enough to compare!!"

    for scenario, expect_fixed in [
        ("transport_error", False),
        ("empty_response", False),
        ("length_guard", False),
        ("success", True),
    ]:
        if scenario == "transport_error":
            def _chat(*_a, **_k):
                raise RuntimeError("backend unreachable")
        else:
            reply = {
                "empty_response": "",
                "length_guard": "x" * (len(content) * 5),
                "success": fixed_text,
            }[scenario]

            def _chat(*_a, _r=reply, **_k):
                return _r

        monkeypatch.setattr(lint.llm, "chat", _chat)
        result = lint.lint_with_llm(content)
        assert result == (fixed_text if expect_fixed else content), f"scenario {scenario}"


def test_unresolved_engine_falls_back_to_original(monkeypatch) -> None:
    """A missing brief / unresolvable engine degrades to the untouched document."""
    def _boom():
        raise RuntimeError("no brief to resolve")

    monkeypatch.setattr(lint, "engine", _boom)
    content = "# Doc\n\nBody long enough to matter."
    assert lint.lint_with_llm(content) == content


def test_chat_is_called_with_the_engine_and_llm_kind(monkeypatch) -> None:
    """The pass forwards the engine, ``kind='llm'`` and temperature 0 to llm.chat."""
    captured: dict = {}

    def _chat(prompt, **kwargs):
        captured["prompt"] = prompt
        captured.update(kwargs)
        return prompt.split("\n\n", 1)[1]  # echo the document back unchanged

    monkeypatch.setattr(lint.llm, "chat", _chat)
    content = "# Title\n\nBody text that is comfortably long enough to pass."
    lint.lint_with_llm(content)

    assert captured["engine"] is _FAKE_ENGINE
    assert captured["kind"] == "llm"
    assert captured["temperature"] == 0.0
    # The prompt carries the strict syntax-only instructions + the document.
    assert "Markdown syntax fixer" in captured["prompt"]
    assert content in captured["prompt"]
