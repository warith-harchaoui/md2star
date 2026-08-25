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

import importlib.util
import io
import shutil
import zipfile
from pathlib import Path

import pytest

_HAS_KREUZBERG = importlib.util.find_spec("kreuzberg") is not None

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


def test_gui_serves_html_bench(client: TestClient) -> None:
    """``/gui`` returns the self-contained HTML conversion bench."""
    r = client.get("/gui")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    # The page must be the md2star bench and must POST to the /convert endpoint.
    assert "md2star — Conversion Bench" in r.text
    assert "/convert" in r.text


def test_root_redirects_to_gui(client: TestClient) -> None:
    """``/`` redirects to the browser bench at ``/gui``."""
    # follow_redirects=False so we assert on the redirect itself, not the target.
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"] == "/gui"


def test_openapi_exposes_expected_routes(client: TestClient) -> None:
    """The OpenAPI schema must list the documented endpoints (drift guard)."""
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/health", "/doctor", "/convert", "/extract"} <= set(paths)


def test_doctor_reports_features(client: TestClient) -> None:
    """``/doctor`` returns the checks + per-format feature map."""
    body = client.get("/doctor").json()
    assert "checks" in body and isinstance(body["checks"], list)
    assert {"docx", "pptx", "pdf", "mermaid"} <= set(body["features"])
    assert isinstance(body["core_failing"], bool)
    # The reverse-conversion availability flag drives the /extract UI.
    assert isinstance(body["reverse_available"], bool)


def test_convert_rejects_unknown_format(client: TestClient) -> None:
    """An unsupported target format yields a 400, not a 500."""
    r = client.post(
        "/convert?fmt=epub",
        files={"file": ("note.md", "# Hi\n", "text/markdown")},
    )
    assert r.status_code == 400


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc not installed")
def test_convert_markdown_to_docx(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A real /convert round-trip returns a non-empty DOCX (ZIP-based) file."""
    # Keep the test hermetic: the API defaults to fetching the deraison.ai
    # template (v2.5.0+) since the staged upload has no local template. Empty
    # the URL map so the resolver skips the network and uses the bundled
    # template — we're asserting the round-trip works, not the fetch path
    # (that lives in tests/test_offline_security.py with a mocked urlopen).
    monkeypatch.setattr("md2star.cli._TEMPLATE_URLS", {}, raising=True)
    md = "# Title\n\nA short paragraph with **bold** text.\n"
    r = client.post(
        "/convert?fmt=docx",
        files={"file": ("note.md", md, "text/markdown")},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats-officedocument")
    # A .docx is a ZIP container — its magic bytes are "PK".
    assert r.content[:2] == b"PK"
    assert len(r.content) > 1000


def test_convert_cleans_up_temp_dir_on_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed ``/convert`` (after the temp dir is staged) must not leak it.

    ``BackgroundTasks`` added via the injected ``background`` parameter are
    silently dropped by FastAPI when the endpoint raises rather than returns
    (verified against a minimal FastAPI app) — so the temp-dir cleanup for the
    failure path can't rely on ``background.add_task`` alone the way the
    success path does; the endpoint must clean up explicitly in its except
    blocks.
    """
    from md2star.errors import Md2starError

    def _boom(fmt, argv):  # noqa: ANN001, ANN202, ARG001
        raise Md2starError("simulated conversion failure")

    monkeypatch.setattr("md2star.api._convert", _boom, raising=True)
    monkeypatch.setattr(
        "md2star.api.osh.make_temporary_directory",
        lambda **_kw: str(tmp_path),
        raising=True,
    )
    r = client.post(
        "/convert?fmt=docx",
        files={"file": ("note.md", "# Hi\n", "text/markdown")},
    )
    assert r.status_code == 500
    assert not tmp_path.exists(), "the temp dir must be removed on a failed /convert"


def test_extract_cleans_up_temp_dir_on_failure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed ``/extract`` (after the temp dir is staged) must not leak it.

    Same reasoning as the ``/convert`` cleanup-on-failure test above.
    """

    def _boom(_path):  # noqa: ANN001, ANN202
        raise RuntimeError("simulated extraction failure")

    monkeypatch.setattr("md2star.reverse.to_markdown", _boom, raising=True)
    monkeypatch.setattr(
        "md2star.api.osh.make_temporary_directory",
        lambda **_kw: str(tmp_path),
        raising=True,
    )
    r = client.post(
        "/extract",
        files={
            "file": (
                "note.docx",
                b"fake-docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert r.status_code == 500
    assert not tmp_path.exists(), "the temp dir must be removed on a failed /extract"


def test_extract_rejects_unsupported_format(client: TestClient) -> None:
    """``/extract`` refuses a non-document upload with a 400 (not a 500)."""
    r = client.post(
        "/extract",
        files={"file": ("note.md", "# Hi\n", "text/markdown")},
    )
    assert r.status_code == 400


def _fake_twin(path, out_dir, *, image_handler=None, **_kw):  # noqa: ANN001, ANN202
    """Stand-in for ``to_markdown_twin``: write a <stem>.md + one asset, offline.

    Lets the twin endpoints be tested without Kreuzberg — it mirrors the real
    contract (a Markdown file plus an ``assets/`` sibling, returning the md path)
    so the zip / sidebar assertions exercise the wiring, not the OCR engine.
    """
    out = Path(out_dir)
    (out / "assets").mkdir(parents=True, exist_ok=True)
    (out / "assets" / "image_1.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    md = out / f"{Path(path).stem}.md"
    md.write_text("# Twin\n\n![](assets/image_1.png)\n", encoding="utf-8")
    return md


def test_extract_text_only_returns_json(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default ``/extract`` (no twin) returns ``{filename, markdown}`` JSON."""
    # Fake the engine so the JSON contract is locked without Kreuzberg installed.
    monkeypatch.setattr("md2star.reverse.to_markdown", lambda _p: "# Recovered\n", raising=True)
    r = client.post(
        "/extract",
        files={
            "file": (
                "note.docx",
                b"fake-docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {"filename": "note.md", "markdown": "# Recovered\n"}


def test_extract_twin_returns_zip(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """``/extract`` with ``twin=true`` streams a zip of <stem>.md + assets/."""
    monkeypatch.setattr("md2star.reverse.to_markdown_twin", _fake_twin, raising=True)
    r = client.post(
        "/extract",
        files={
            "file": (
                "note.docx",
                b"fake-docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"twin": "true"},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    # The zip must carry both the recovered markdown and the scraped asset, with
    # the assets/ prefix preserved so the archived links keep resolving.
    names = set(zipfile.ZipFile(io.BytesIO(r.content)).namelist())
    assert names == {"note.md", "assets/image_1.png"}


@pytest.mark.skipif(
    shutil.which("pandoc") is None or not _HAS_KREUZBERG,
    reason="reverse round-trip needs pandoc (forward) + kreuzberg (reverse)",
)
def test_extract_docx_roundtrips_to_markdown(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DOCX produced by /convert is read back to Markdown by /extract."""
    monkeypatch.setattr("md2star.cli._TEMPLATE_URLS", {}, raising=True)
    # Forward: Markdown → DOCX.
    fwd = client.post(
        "/convert?fmt=docx",
        files={"file": ("note.md", "# Heading One\n\nA **bold** word.\n", "text/markdown")},
    )
    assert fwd.status_code == 200, fwd.text
    # Reverse: DOCX → Markdown.
    rev = client.post(
        "/extract",
        files={
            "file": (
                "note.docx",
                fwd.content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert rev.status_code == 200, rev.text
    body = rev.json()
    assert body["filename"] == "note.md"
    assert "Heading One" in body["markdown"]
    assert "bold" in body["markdown"]
