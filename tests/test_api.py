"""
Smoke + round-trip tests for the FastAPI HTTP surface (``md2star.api``).

Exercises the endpoints that do not need heavy setup — ``/health``, ``/doctor``,
OpenAPI schema introspection (to catch route drift), and the ``/convert`` 400
path for an unknown format — plus a real ``/convert`` round-trip to DOCX that is
skipped when Pandoc is absent from the host.

Usage Example
-------------
>>> #   pytest tests/test_api.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import shutil

import pytest

# FastAPI + httpx live in the [api] / [dev] extras — skip cleanly otherwise.
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Yield a TestClient bound to the md2star FastAPI app."""
    from md2star.api import app

    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client: TestClient) -> None:
    """``/health`` returns 200 + ``{"status": "ok"}``."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_exposes_expected_routes(client: TestClient) -> None:
    """The OpenAPI schema must list the documented endpoints (drift guard)."""
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/health", "/doctor", "/convert"} <= set(paths)


def test_doctor_reports_features(client: TestClient) -> None:
    """``/doctor`` returns the checks + per-format feature map."""
    body = client.get("/doctor").json()
    assert "checks" in body and isinstance(body["checks"], list)
    assert {"docx", "pptx", "pdf", "mermaid"} <= set(body["features"])
    assert isinstance(body["core_failing"], bool)


def test_convert_rejects_unknown_format(client: TestClient) -> None:
    """An unsupported target format yields a 400, not a 500."""
    r = client.post(
        "/convert?fmt=epub",
        files={"file": ("note.md", "# Hi\n", "text/markdown")},
    )
    assert r.status_code == 400


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_convert_markdown_to_docx(client: TestClient) -> None:
    """A real /convert round-trip returns a non-empty DOCX (ZIP-based) file."""
    md = "# Title\n\nA short paragraph with **bold** text.\n"
    r = client.post(
        "/convert?fmt=docx",
        files={"file": ("note.md", md, "text/markdown")},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    # A .docx is a ZIP container — its magic bytes are "PK".
    assert r.content[:2] == b"PK"
    assert len(r.content) > 1000
