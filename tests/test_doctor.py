"""Unit tests for md2star.doctor.

The diagnostic logic is decoupled from terminal rendering, so we
inject a fake ``which`` to simulate any combination of dependencies
being present or missing without touching the real PATH.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from md2star import doctor


# Helper: a ``which`` substitute that returns a fixed mapping.
def fake_which(present: dict[str, str | None]):
    """Return a ``which``-like callable that maps a binary name to its path."""
    def _which(name: str) -> str | None:
        return present.get(name)
    return _which


# Patch _run_version everywhere so the tests don't actually shell out
# to whatever ``pandoc`` / ``soffice`` happens to be on the test
# machine (which would make assertions flaky). Also neutralise the
# macOS ``/Applications/LibreOffice.app`` filesystem fallback in
# _check_libreoffice — on a dev machine that *has* LibreOffice
# installed, the fallback would beat the injected ``which`` and break
# the "missing dependency" assertions.
@pytest.fixture(autouse=True)
def _no_version_shellout(monkeypatch):
    monkeypatch.setattr(
        doctor, "_run_version",
        lambda cmd, **kw: f"{cmd[0]} fake-version-for-tests",
    )
    # Force Path.exists to return False for the macOS LibreOffice.app
    # fallback so test_soffice_missing_pdf_is_partial holds regardless
    # of the host environment. Other Path.exists calls are passed
    # through unchanged.
    from pathlib import Path
    real_exists = Path.exists
    def _patched_exists(self):
        if str(self) == "/Applications/LibreOffice.app/Contents/MacOS/soffice":
            return False
        return real_exists(self)
    monkeypatch.setattr(Path, "exists", _patched_exists)


class TestCorePresent:
    """The healthy baseline: pandoc + everything optional."""

    def test_all_dependencies_present(self):
        present = {
            "pandoc": "/usr/bin/pandoc",
            "soffice": "/usr/bin/soffice",
            "node": "/usr/bin/node",
            "npx": "/usr/bin/npx",
            "mmdc": "/usr/local/bin/mmdc",
            "ollama": "/usr/bin/ollama",
        }
        report = doctor.run_checks(which=fake_which(present))
        assert report.get("Pandoc").status == doctor.STATUS_OK
        assert report.get("LibreOffice").status == doctor.STATUS_OK
        assert report.get("Node.js").status == doctor.STATUS_OK
        assert report.get("Mermaid CLI").status == doctor.STATUS_OK
        assert report.get("Ollama").status == doctor.STATUS_OK
        assert report.core_failing() is False
        assert report.feature_status("pdf") == doctor.STATUS_OK
        assert report.feature_status("mermaid") == doctor.STATUS_OK


class TestPandocMissing:
    """Pandoc missing is a Core failure — exit code 1."""

    def test_pandoc_missing_marks_core_failing(self):
        report = doctor.run_checks(which=fake_which({}))
        assert report.get("Pandoc").status == doctor.STATUS_MISSING
        assert report.core_failing() is True
        # Every conversion target degrades.
        assert report.feature_status("docx") == "UNAVAILABLE"
        assert report.feature_status("pptx") == "UNAVAILABLE"
        assert report.feature_status("pdf")  == "UNAVAILABLE"

    def test_pandoc_missing_returns_exit_1(self, capsys):
        with patch.object(doctor, "run_checks", return_value=_make_report_missing_pandoc()):
            rc = doctor.main([])
        assert rc == 1
        out = capsys.readouterr().out
        assert "Pandoc" in out and "MISSING" in out


class TestOptionalMissing:
    """Soffice / Node / Ollama missing → degraded but not failing."""

    def test_soffice_missing_pdf_is_partial(self):
        report = doctor.run_checks(which=fake_which({"pandoc": "/usr/bin/pandoc"}))
        assert report.get("LibreOffice").status == doctor.STATUS_MISSING
        assert report.core_failing() is False
        assert report.feature_status("pdf") == "PARTIAL"
        assert report.feature_status("docx") == doctor.STATUS_OK   # pandoc alone is enough

    def test_node_missing_mermaid_unavailable(self):
        report = doctor.run_checks(which=fake_which({"pandoc": "/usr/bin/pandoc"}))
        assert report.get("Node.js").status == doctor.STATUS_INFO
        assert report.feature_status("mermaid") == "UNAVAILABLE"

    def test_npx_alone_is_acceptable_for_mermaid(self):
        # Real-world: Node installed via brew/apt comes with npx but
        # mmdc isn't globally installed; md2star uses `npx -y mmdc` lazily.
        present = {"pandoc": "/p", "node": "/n", "npx": "/x"}
        report = doctor.run_checks(which=fake_which(present))
        assert report.get("Mermaid CLI").status == doctor.STATUS_INFO
        assert "npx" in report.get("Mermaid CLI").detail


class TestExitCode:
    """The CLI returns 0 unless Core is broken."""

    def test_returns_0_when_only_optional_missing(self):
        with patch.object(doctor, "run_checks",
                          return_value=_make_report_only_pandoc()):
            assert doctor.main([]) == 0


class TestJsonOutput:
    """--json emits a stable shape downstream tools can parse."""

    def test_json_shape(self, capsys):
        report = _make_report_only_pandoc()
        with patch.object(doctor, "run_checks", return_value=report):
            rc = doctor.main(["--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["core_failing"] is False
        assert "features" in payload and "pdf" in payload["features"]
        assert any(c["name"] == "Pandoc" for c in payload["checks"])


class TestRenderedOutput:
    """Human-readable output is scannable + includes a Result footer."""

    def test_render_includes_result_section(self):
        report = doctor.run_checks(which=fake_which({"pandoc": "/p"}))
        text = doctor.render(report)
        assert "Core:" in text
        assert "Optional:" in text
        assert "Templates:" in text
        assert "Result:" in text
        assert "DOCX export" in text and "PDF export" in text


# ─────────────────────────────────────────────────────────────────────
# Helpers used by the patches above
# ─────────────────────────────────────────────────────────────────────


def _make_report_missing_pandoc() -> doctor.Report:
    r = doctor.Report()
    r.add("Pandoc", doctor.STATUS_MISSING, "fake — install pandoc")
    return r


def _make_report_only_pandoc() -> doctor.Report:
    r = doctor.Report()
    r.add("Python", doctor.STATUS_OK, "3.12.0")
    r.add("md2star", doctor.STATUS_OK, "test")
    r.add("Pandoc", doctor.STATUS_OK, "fake 3.x")
    r.add("LibreOffice", doctor.STATUS_MISSING, "", section="Optional")
    return r
