"""Functional tests for the opt-in Ollama lint pass (``md2star.preprocessing.lint``).

Every path in this module talks to a local Ollama daemon over HTTP or spawns
the ``ollama`` binary, so the whole module is exercised here with those two
boundaries mocked — no daemon, no binary, fully deterministic. The design
contract under test is that lint is **never load-bearing**: whatever goes wrong
(binary missing, daemon down, model absent, junk response), the original
Markdown is returned unchanged so the surrounding conversion still succeeds.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from md2star.preprocessing import lint


@contextmanager
def _fake_http(payload: dict):
    """Yield a stand-in for ``urlopen(...)`` returning *payload* as JSON.

    Parameters
    ----------
    payload : dict
        The object the fake endpoint should serialize and return from
        ``.read()``, mimicking an Ollama HTTP response.

    Yields
    ------
    object
        A context-manager-compatible response whose ``read()`` returns the
        UTF-8 JSON encoding of *payload*.
    """
    # Minimal object with just the .read() the module uses; the outer
    # contextmanager supplies the __enter__/__exit__ that `with urlopen(...)`
    # needs, so we don't have to hand-roll them.
    class _Resp:
        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    yield _Resp()


# ── _model_present drives the real _fetch_ollama_models over a mocked socket ──
@pytest.mark.parametrize(
    ("installed", "query", "expected"),
    [
        # Exact tag match is the common hit.
        (["gemma4:e2b"], "gemma4:e2b", True),
        # Untagged query tolerates the ``:latest`` form Ollama stores.
        (["gemma4:latest"], "gemma4", True),
        # Genuinely-absent model → False (daemon reachable, just missing it).
        (["other:latest"], "gemma4:e2b", False),
    ],
)
def test_model_present_matches_tags(monkeypatch, installed, query, expected) -> None:
    """``_model_present`` honors exact and ``:latest``-implied tag matches.

    Routing through the real ``_fetch_ollama_models`` (only the socket is
    faked) covers the tag-list parsing and the empty-name filtering too.
    """
    # Fake /api/tags to advertise exactly the `installed` models.
    models = {"models": [{"name": n} for n in installed] + [{"name": ""}]}
    monkeypatch.setattr(
        lint.urllib.request, "urlopen", lambda *a, **k: _fake_http(models)
    )
    assert lint._model_present(query) is expected


def test_fetch_models_returns_none_when_daemon_unreachable(monkeypatch) -> None:
    """An unreachable daemon degrades to ``None``, never an exception.

    Callers treat ``None`` as "no models"; this is what lets the whole lint
    pass stay best-effort instead of surfacing a connection error.
    """
    # Any urlopen error must be swallowed into a None return.
    def _boom(*_a, **_k):
        raise OSError("connection refused")

    monkeypatch.setattr(lint.urllib.request, "urlopen", _boom)
    assert lint._fetch_ollama_models() is None
    assert lint._ping_ollama() is False


@pytest.mark.parametrize(
    ("present", "run_rc", "run_exc", "expected"),
    [
        # Already pulled → short-circuits to True without shelling out.
        (True, None, None, True),
        # Missing then a clean pull (rc 0) → True.
        (False, 0, None, True),
        # Missing then a failed pull (rc 1) → False, non-fatal.
        (False, 1, None, False),
        # Missing then the binary vanishes mid-pull → False, non-fatal.
        (False, None, FileNotFoundError("ollama"), False),
    ],
)
def test_ensure_model_pulled(monkeypatch, present, run_rc, run_exc, expected) -> None:
    """``_ensure_model_pulled`` pulls on demand and never raises on failure.

    Parameters
    ----------
    present : bool
        Whether the model is reported already-present (skips the pull).
    run_rc : int or None
        Return code of the mocked ``ollama pull`` (ignored when *present*).
    run_exc : Exception or None
        Exception the mocked ``subprocess.run`` should raise instead.
    expected : bool
        The expected boolean result.
    """
    # Steer the presence check without touching the network.
    monkeypatch.setattr(lint, "_model_present", lambda *_a, **_k: present)

    # Fake `ollama pull` to either raise, or return an object with .returncode.
    def _fake_run(*_a, **_k):
        if run_exc is not None:
            raise run_exc
        return type("P", (), {"returncode": run_rc, "stderr": b""})()

    monkeypatch.setattr(lint.subprocess, "run", _fake_run)
    assert lint._ensure_model_pulled("gemma4:e2b") is expected


def test_ensure_running_spawns_then_gives_up(monkeypatch) -> None:
    """``_ensure_ollama_running`` returns False when a spawned daemon never answers.

    Covers the spawn branch: ping fails, we Popen ``ollama serve``, then poll
    and still get no answer — best-effort, so it gives up with False.
    """
    # Daemon never answers the ping; skip real sleeping between polls.
    monkeypatch.setattr(lint, "_ping_ollama", lambda *_a, **_k: False)
    monkeypatch.setattr(lint.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(lint.subprocess, "Popen", lambda *_a, **_k: None)
    assert lint._ensure_ollama_running() is False


# ── lint_with_llm: the public entry point and its full fallback ladder ──
@pytest.mark.parametrize(
    ("scenario", "expect_fixed"),
    [
        ("not_installed", False),   # ollama binary absent → original kept
        ("daemon_down", False),     # daemon unreachable → original kept
        ("model_missing", False),   # pull fails → original kept
        ("empty_response", False),  # blank model output → original kept
        ("length_guard", False),    # wildly-long output → distrusted, original kept
        ("request_error", False),   # HTTP error mid-request → original kept
        ("success", True),          # sane output → model's fixed markdown returned
    ],
)
def test_lint_with_llm_fallback_ladder(monkeypatch, scenario, expect_fixed) -> None:
    """Every failure mode falls back to the original; only a sane fix is applied.

    Parameters
    ----------
    scenario : str
        Which rung of the resolution ladder to exercise.
    expect_fixed : bool
        True only for the happy path where the model's output replaces the
        input; every other scenario must return the input verbatim.
    """
    content = "# Title\n\nSome body text that is long enough to compare."
    fixed_text = "# Title\n\nSome body text that is long enough to compare!!"

    # Default every gate to "reachable"; each scenario knocks out one rung.
    monkeypatch.setattr(lint, "is_ollama_installed", lambda: scenario != "not_installed")
    monkeypatch.setattr(
        lint, "_ensure_ollama_running", lambda: scenario != "daemon_down"
    )
    monkeypatch.setattr(
        lint, "_ensure_model_pulled", lambda *_a, **_k: scenario != "model_missing"
    )

    # Shape the final HTTP response per scenario (only reached past the gates).
    responses = {
        "empty_response": {"response": ""},
        "length_guard": {"response": "x" * (len(content) * 5)},
        "success": {"response": fixed_text},
    }
    if scenario == "request_error":
        def _urlopen(*_a, **_k):
            raise OSError("socket died")
        monkeypatch.setattr(lint.urllib.request, "urlopen", _urlopen)
    else:
        payload = responses.get(scenario, {"response": fixed_text})
        monkeypatch.setattr(
            lint.urllib.request, "urlopen", lambda *a, **k: _fake_http(payload)
        )

    result = lint.lint_with_llm(content, model="gemma4:e2b")

    # Happy path returns the model's text; every other rung keeps the original.
    assert result == (fixed_text if expect_fixed else content)
