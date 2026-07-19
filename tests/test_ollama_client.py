"""Tests for the optional Ollama client layer (``md2star[ai]`` extra).

The layer (:mod:`md2star.preprocessing._ollama_client`) has two jobs: wrap the
official ``ollama`` client when the ``[ai]`` extra is installed, and stay out
of the way (return ``None`` so callers use their urllib fallback) when it is
not. The real ``ollama`` package is *not* a test dependency, so every client
path here is exercised against an injected fake — that keeps these tests
deterministic and offline while still proving both response shapes, the
failure-swallowing contract, and that :mod:`lint` / :mod:`alt_text` actually
route through the client when ``OLLAMA`` is present.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import types

import pytest

from md2star.preprocessing import _ollama_client, alt_text, lint


class _FakeClient:
    """Stand-in for ``ollama.Client`` recording construction + call args.

    Its ``list``/``generate`` return whatever the enclosing fake module was
    seeded with, or raise if seeded with an exception — enough to drive both
    the success and error branches of the wrapper.
    """

    def __init__(self, *, list_ret=None, gen_ret=None, timeout=None) -> None:
        # Remember the timeout so a test can assert the caller's value is honored.
        self.timeout = timeout
        self._list_ret = list_ret
        self._gen_ret = gen_ret
        self.generate_calls: list[dict] = []

    def list(self):
        """Return (or raise) the seeded ``ollama.list()`` payload."""
        if isinstance(self._list_ret, Exception):
            raise self._list_ret
        return self._list_ret

    def generate(self, **kwargs):
        """Record the call, then return (or raise) the seeded payload."""
        self.generate_calls.append(kwargs)
        if isinstance(self._gen_ret, Exception):
            raise self._gen_ret
        return self._gen_ret


def _fake_ollama_module(**client_kwargs) -> types.SimpleNamespace:
    """Build a fake ``ollama`` module whose ``Client(...)`` yields our stub.

    The wrapper constructs ``OLLAMA.Client(timeout=...)`` per call, so exposing
    a ``Client`` factory that captures the last-built instance lets tests both
    seed return values and inspect what the wrapper passed in.
    """
    captured: dict = {}

    def _factory(*, timeout=None):
        client = _FakeClient(timeout=timeout, **client_kwargs)
        captured["client"] = client
        return client

    return types.SimpleNamespace(Client=_factory, _captured=captured)


# ── list_model_names ─────────────────────────────────────────────────────────
def test_list_model_names_none_without_extra(monkeypatch) -> None:
    """No extra installed (``OLLAMA is None``) → ``None`` so callers fall back."""
    monkeypatch.setattr(_ollama_client, "OLLAMA", None)
    assert _ollama_client.list_model_names() is None


@pytest.mark.parametrize(
    "payload",
    [
        # Typed ``ListResponse``-style: objects exposing ``.model``.
        types.SimpleNamespace(
            models=[types.SimpleNamespace(model="gemma4:e2b"),
                    types.SimpleNamespace(model="")]
        ),
        # Raw dict payload with the modern ``model`` key…
        {"models": [{"model": "gemma4:e2b"}, {"model": ""}]},
        # …and the legacy ``name`` key both parse to the same tag list.
        {"models": [{"name": "gemma4:e2b"}, {"name": ""}]},
    ],
)
def test_list_model_names_parses_shapes(monkeypatch, payload) -> None:
    """Both typed and dict (modern + legacy) shapes yield the tag list."""
    monkeypatch.setattr(
        _ollama_client, "OLLAMA", _fake_ollama_module(list_ret=payload)
    )
    # Empty names are filtered out, leaving just the real tag.
    assert _ollama_client.list_model_names() == ["gemma4:e2b"]


def test_list_model_names_swallows_errors(monkeypatch) -> None:
    """A daemon/socket error is swallowed into ``None`` (never raised)."""
    monkeypatch.setattr(
        _ollama_client,
        "OLLAMA",
        _fake_ollama_module(list_ret=ConnectionError("daemon down")),
    )
    assert _ollama_client.list_model_names() is None


# ── generate ─────────────────────────────────────────────────────────────────
def test_generate_none_without_extra(monkeypatch) -> None:
    """No extra installed → ``None`` so the caller takes its urllib path."""
    monkeypatch.setattr(_ollama_client, "OLLAMA", None)
    assert _ollama_client.generate("m", "hi") is None


@pytest.mark.parametrize(
    "payload",
    [
        types.SimpleNamespace(response="  fixed text  "),  # typed response
        {"response": "  fixed text  "},                     # dict response
    ],
)
def test_generate_trims_and_passes_args(monkeypatch, payload) -> None:
    """Response is trimmed; model/prompt/images/options reach the client."""
    fake = _fake_ollama_module(gen_ret=payload)
    monkeypatch.setattr(_ollama_client, "OLLAMA", fake)

    out = _ollama_client.generate(
        "gemma4:e2b", "prompt", images=["/img.png"], options={"temperature": 0.2}
    )
    assert out == "fixed text"
    # The wrapper must forward every field the urllib path used to POST.
    call = fake._captured["client"].generate_calls[0]
    assert call["model"] == "gemma4:e2b"
    assert call["prompt"] == "prompt"
    assert call["images"] == ["/img.png"]
    assert call["options"] == {"temperature": 0.2}
    assert call["stream"] is False


def test_generate_empty_response_is_none(monkeypatch) -> None:
    """Whitespace-only output normalises to ``None`` (keep the original)."""
    monkeypatch.setattr(
        _ollama_client, "OLLAMA", _fake_ollama_module(gen_ret={"response": "   "})
    )
    assert _ollama_client.generate("m", "p") is None


def test_generate_swallows_errors(monkeypatch) -> None:
    """Any client exception degrades to ``None`` rather than propagating."""
    monkeypatch.setattr(
        _ollama_client,
        "OLLAMA",
        _fake_ollama_module(gen_ret=RuntimeError("model exploded")),
    )
    assert _ollama_client.generate("m", "p") is None


# ── integration: callers route through the client when it is present ──────────
def test_lint_fetch_models_uses_client(monkeypatch) -> None:
    """``lint._fetch_ollama_models`` prefers the client over urllib."""
    monkeypatch.setattr(
        _ollama_client, "OLLAMA", _fake_ollama_module(list_ret={"models": [
            {"model": "gemma4:e2b"}]})
    )
    # If this hit urllib instead, there is no daemon and it would return None.
    assert lint._fetch_ollama_models() == ["gemma4:e2b"]


def test_lint_with_llm_uses_client(monkeypatch) -> None:
    """``lint_with_llm`` applies a client-produced fix through the gates."""
    monkeypatch.setattr(
        _ollama_client, "OLLAMA", _fake_ollama_module(gen_ret={
            "response": "# Fixed heading\n\nBody paragraph."})
    )
    # Pass the gating helpers (binary/daemon/model) so we reach the generate.
    monkeypatch.setattr(lint, "is_ollama_installed", lambda: True)
    monkeypatch.setattr(lint, "_ensure_ollama_running", lambda: True)
    monkeypatch.setattr(lint, "_ensure_model_pulled", lambda *_a, **_k: True)

    out = lint.lint_with_llm("# heading\n\nBody paragraph.")
    assert out == "# Fixed heading\n\nBody paragraph."


def test_generate_alt_uses_client(monkeypatch, tmp_path) -> None:
    """``alt_text._generate_alt`` routes the image through the client."""
    fake = _fake_ollama_module(gen_ret={"response": '"A red bicycle."'})
    monkeypatch.setattr(_ollama_client, "OLLAMA", fake)
    img = tmp_path / "pic.png"
    img.write_bytes(b"not-a-real-png")  # never read: the client owns encoding

    # Surrounding quotes are stripped by the shared cleanup on both paths.
    assert alt_text._generate_alt(str(img), "gemma4:e2b") == "A red bicycle."
    # The image path (not base64) is what the client receives.
    assert fake._captured["client"].generate_calls[0]["images"] == [str(img)]
