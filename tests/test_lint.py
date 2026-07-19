"""Functional tests for the opt-in Ollama lint pass (``md2star.preprocessing.lint``).

Every path talks to a local Ollama daemon over HTTP or spawns the ``ollama``
binary, so the module is exercised with those two boundaries mocked — no daemon,
no binary, fully deterministic. The contract under test is that lint is **never
load-bearing**: whatever goes wrong (binary missing, daemon down, model absent,
junk response), the original Markdown is returned unchanged. Each test drives a
whole family of cases through the real functions so a few tests cover the entire
resolution ladder.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest

from md2star.preprocessing import lint


@pytest.fixture(autouse=True)
def _force_urllib_transport(monkeypatch) -> None:
    """Pin these tests to the zero-dependency urllib transport.

    They mock ``urlopen`` to drive the fallback path, so if the ``md2star[ai]``
    extra is installed we force ``_ollama_client.OLLAMA`` to ``None``; the client
    path is covered in ``test_ollama_client.py``.
    """
    monkeypatch.setattr(lint._ollama_client, "OLLAMA", None)


@contextmanager
def _fake_http(payload: dict):
    """Yield a ``urlopen(...)`` stand-in whose ``.read()`` returns *payload* JSON."""
    class _Resp:
        def read(self) -> bytes:
            return json.dumps(payload).encode("utf-8")

    yield _Resp()


def test_model_discovery_over_mocked_socket(monkeypatch) -> None:
    """``_model_present`` / ``_fetch_ollama_models`` / ``_ping_ollama`` end to end.

    Drives tag matching (exact + ``:latest``-implied + genuinely absent) and the
    daemon-unreachable degradation through the real functions, faking only the
    socket.
    """
    # Tag-match matrix: exact hit, untagged tolerates :latest, absent → False.
    for installed, query, expected in [
        (["gemma4:e2b"], "gemma4:e2b", True),
        (["gemma4:latest"], "gemma4", True),
        (["other:latest"], "gemma4:e2b", False),
    ]:
        models = {"models": [{"name": n} for n in installed] + [{"name": ""}]}
        monkeypatch.setattr(lint.urllib.request, "urlopen", lambda *a, _m=models, **k: _fake_http(_m))
        assert lint._model_present(query) is expected

    # An unreachable daemon degrades to None / False, never an exception.
    def _boom(*_a, **_k):
        raise OSError("connection refused")

    monkeypatch.setattr(lint.urllib.request, "urlopen", _boom)
    assert lint._fetch_ollama_models() is None
    assert lint._ping_ollama() is False


def test_ensure_model_pulled_all_outcomes(monkeypatch) -> None:
    """``_ensure_model_pulled`` pulls on demand and never raises on failure.

    Covers: already-present (no shell-out), clean pull (rc 0), failed pull
    (rc 1), and the binary vanishing mid-pull — the last three via a faked
    ``subprocess.run``.
    """
    for present, run_rc, run_exc, expected in [
        (True, None, None, True),                       # already pulled
        (False, 0, None, True),                         # clean pull
        (False, 1, None, False),                        # failed pull, non-fatal
        (False, None, FileNotFoundError("ollama"), False),  # binary vanished
    ]:
        monkeypatch.setattr(lint, "_model_present", lambda *_a, _p=present, **_k: _p)

        def _fake_run(*_a, _rc=run_rc, _exc=run_exc, **_k):
            if _exc is not None:
                raise _exc
            return type("P", (), {"returncode": _rc, "stderr": b""})()

        monkeypatch.setattr(lint.subprocess, "run", _fake_run)
        assert lint._ensure_model_pulled("gemma4:e2b") is expected


def test_ensure_running_spawns_then_gives_up(monkeypatch) -> None:
    """``_ensure_ollama_running`` returns False when a spawned daemon never answers."""
    # Daemon never answers the ping; skip real sleeping between polls.
    monkeypatch.setattr(lint, "_ping_ollama", lambda *_a, **_k: False)
    monkeypatch.setattr(lint.time, "sleep", lambda *_a, **_k: None)
    monkeypatch.setattr(lint.subprocess, "Popen", lambda *_a, **_k: None)
    assert lint._ensure_ollama_running() is False


def test_lint_with_llm_fallback_ladder(monkeypatch) -> None:
    """Every failure mode falls back to the original; only a sane fix is applied.

    Walks the whole ladder — binary absent, daemon down, model missing, empty
    output, length-guard trip, request error, and the happy path — asserting the
    input is returned verbatim except when the model returns sane output.
    """
    content = "# Title\n\nSome body text that is long enough to compare."
    fixed_text = "# Title\n\nSome body text that is long enough to compare!!"

    for scenario, expect_fixed in [
        ("not_installed", False), ("daemon_down", False), ("model_missing", False),
        ("empty_response", False), ("length_guard", False), ("request_error", False),
        ("success", True),
    ]:
        # Default every gate to reachable; each scenario knocks out one rung.
        monkeypatch.setattr(lint, "is_ollama_installed", lambda _s=scenario: _s != "not_installed")
        monkeypatch.setattr(lint, "_ensure_ollama_running", lambda _s=scenario: _s != "daemon_down")
        monkeypatch.setattr(lint, "_ensure_model_pulled", lambda *_a, _s=scenario, **_k: _s != "model_missing")

        # Shape the HTTP response per scenario (only reached past the gates).
        if scenario == "request_error":
            def _urlopen(*_a, **_k):
                raise OSError("socket died")
            monkeypatch.setattr(lint.urllib.request, "urlopen", _urlopen)
        else:
            payload = {
                "empty_response": {"response": ""},
                "length_guard": {"response": "x" * (len(content) * 5)},
                "success": {"response": fixed_text},
            }.get(scenario, {"response": fixed_text})
            monkeypatch.setattr(lint.urllib.request, "urlopen",
                                lambda *a, _p=payload, **k: _fake_http(_p))

        result = lint.lint_with_llm(content, model="gemma4:e2b")
        assert result == (fixed_text if expect_fixed else content), f"scenario {scenario}"
