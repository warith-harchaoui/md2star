"""Tests for the optional Ollama client layer (``md2star[ai]`` extra).

The layer wraps the official ``ollama`` client when the ``[ai]`` extra is present
and returns ``None`` (so callers use their urllib fallback) when it is not. The
real package is not a test dependency, so every client path is driven by an
injected fake — deterministic and offline. Three functional tests cover the
whole surface: the two public helpers across both response shapes and the
failure contract, plus proof that lint/alt_text actually route through them.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import types

from md2star.preprocessing import _ollama_client, alt_text, lint


class _FakeClient:
    """Stand-in for ``ollama.Client`` recording construction + call args."""

    def __init__(self, *, list_ret=None, gen_ret=None, timeout=None) -> None:
        self.timeout = timeout
        self._list_ret = list_ret
        self._gen_ret = gen_ret
        self.generate_calls: list[dict] = []

    def list(self):
        if isinstance(self._list_ret, Exception):
            raise self._list_ret
        return self._list_ret

    def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        if isinstance(self._gen_ret, Exception):
            raise self._gen_ret
        return self._gen_ret


def _fake_ollama(**client_kwargs) -> types.SimpleNamespace:
    """Build a fake ``ollama`` module whose ``Client(...)`` yields our stub."""
    captured: dict = {}

    def _factory(*, timeout=None):
        client = _FakeClient(timeout=timeout, **client_kwargs)
        captured["client"] = client
        return client

    return types.SimpleNamespace(Client=_factory, _captured=captured)


def test_list_model_names_all_paths(monkeypatch) -> None:
    """None without the extra; parses typed + dict + legacy shapes; swallows errors."""
    # No extra installed → None so callers fall back to urllib.
    monkeypatch.setattr(_ollama_client, "OLLAMA", None)
    assert _ollama_client.list_model_names() is None

    # Every response shape (typed ``.model`` objects, modern ``model`` dicts, and
    # the legacy ``name`` key) parses to the same non-empty tag list.
    shapes = [
        types.SimpleNamespace(models=[types.SimpleNamespace(model="gemma4:e2b"),
                                      types.SimpleNamespace(model="")]),
        {"models": [{"model": "gemma4:e2b"}, {"model": ""}]},
        {"models": [{"name": "gemma4:e2b"}, {"name": ""}]},
    ]
    for payload in shapes:
        monkeypatch.setattr(_ollama_client, "OLLAMA", _fake_ollama(list_ret=payload))
        assert _ollama_client.list_model_names() == ["gemma4:e2b"]

    # A daemon/socket error is swallowed into None, never raised.
    monkeypatch.setattr(_ollama_client, "OLLAMA", _fake_ollama(list_ret=ConnectionError("down")))
    assert _ollama_client.list_model_names() is None


def test_generate_all_paths(monkeypatch) -> None:
    """None without the extra; trims + forwards args (both shapes); empty→None; swallows errors."""
    monkeypatch.setattr(_ollama_client, "OLLAMA", None)
    assert _ollama_client.generate("m", "hi") is None

    # Typed and dict responses both trim to the same text, and every field the
    # urllib path used to POST reaches the client.
    for payload in (types.SimpleNamespace(response="  fixed  "), {"response": "  fixed  "}):
        fake = _fake_ollama(gen_ret=payload)
        monkeypatch.setattr(_ollama_client, "OLLAMA", fake)
        out = _ollama_client.generate("gemma4:e2b", "p", images=["/i.png"], options={"temperature": 0.2})
        assert out == "fixed"
        call = fake._captured["client"].generate_calls[0]
        assert call["model"] == "gemma4:e2b" and call["prompt"] == "p"
        assert call["images"] == ["/i.png"] and call["options"] == {"temperature": 0.2}
        assert call["stream"] is False

    # Whitespace-only output normalises to None; any exception degrades to None.
    monkeypatch.setattr(_ollama_client, "OLLAMA", _fake_ollama(gen_ret={"response": "   "}))
    assert _ollama_client.generate("m", "p") is None
    monkeypatch.setattr(_ollama_client, "OLLAMA", _fake_ollama(gen_ret=RuntimeError("boom")))
    assert _ollama_client.generate("m", "p") is None


def test_callers_route_through_client(monkeypatch, tmp_path) -> None:
    """lint._fetch_ollama_models, lint_with_llm, and alt_text._generate_alt use the client."""
    # Model listing prefers the client over urllib.
    monkeypatch.setattr(_ollama_client, "OLLAMA",
                        _fake_ollama(list_ret={"models": [{"model": "gemma4:e2b"}]}))
    assert lint._fetch_ollama_models() == ["gemma4:e2b"]

    # lint applies a client-produced fix through the gates.
    monkeypatch.setattr(_ollama_client, "OLLAMA",
                        _fake_ollama(gen_ret={"response": "# Fixed\n\nBody."}))
    monkeypatch.setattr(lint, "is_ollama_installed", lambda: True)
    monkeypatch.setattr(lint, "_ensure_ollama_running", lambda: True)
    monkeypatch.setattr(lint, "_ensure_model_pulled", lambda *_a, **_k: True)
    assert lint.lint_with_llm("# h\n\nBody.") == "# Fixed\n\nBody."

    # alt-text hands the image *path* to the client; shared cleanup strips quotes.
    fake = _fake_ollama(gen_ret={"response": '"A red bicycle."'})
    monkeypatch.setattr(_ollama_client, "OLLAMA", fake)
    img = tmp_path / "pic.png"
    img.write_bytes(b"not-a-real-png")
    assert alt_text._generate_alt(str(img), "gemma4:e2b") == "A red bicycle."
    assert fake._captured["client"].generate_calls[0]["images"] == [str(img)]
