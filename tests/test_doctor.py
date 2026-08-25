"""Unit tests for md2star.doctor.

The diagnostic logic is decoupled from terminal rendering, so we inject
a fake ``which`` to simulate any combination of dependencies being
present or missing without touching the real PATH.

The suite is organised by behaviour:

* :class:`TestDiagnosis` drives ``run_checks`` over realistic dependency
  environments — a fully healthy machine and one with only pandoc — and
  a parametrised sweep of the "which optional tool is missing?" matrix,
  asserting per-check status *and* the derived feature availability.
* :class:`TestCli` covers the ``main``/``render`` surface: the JSON
  shape, the human-readable render, and the exit-code contract. The
  "pandoc missing → exit 1" contract is kept standalone because it is
  the load-bearing regression the CLI exists to guarantee.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from md2star import doctor


# Helper: a ``which`` substitute that returns a fixed mapping.
def fake_which(present: dict[str, str | None]):
    """Return a ``which``-like callable over a fixed name→path mapping.

    Parameters
    ----------
    present : dict[str, str | None]
        Binary name → resolved path (or ``None`` for absent).

    Returns
    -------
    Callable[[str], str | None]
        A drop-in replacement for :func:`shutil.which`.
    """

    def _which(name: str) -> str | None:
        return present.get(name)

    return _which


# Patch _run_version everywhere so the tests don't actually shell out to
# whatever ``pandoc`` / ``soffice`` happens to be on the test machine
# (which would make assertions flaky). Also neutralise the macOS
# ``/Applications/LibreOffice.app`` filesystem fallback in
# _check_libreoffice — on a dev machine that *has* LibreOffice installed,
# the fallback would beat the injected ``which`` and break the "missing
# dependency" assertions.
@pytest.fixture(autouse=True)
def _no_version_shellout(monkeypatch):
    """Stub version probing and the macOS LibreOffice.app path fallback.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to replace ``doctor._run_version`` and ``Path.exists``.
    """
    monkeypatch.setattr(
        doctor,
        "_run_version",
        lambda cmd, **kw: f"{cmd[0]} fake-version-for-tests",
    )
    # Force Path.exists to return False for the macOS LibreOffice.app
    # fallback so the "soffice missing" assertions hold regardless of the
    # host environment. Other Path.exists calls are passed through.
    from pathlib import Path

    real_exists = Path.exists

    def _patched_exists(self):
        if str(self) == "/Applications/LibreOffice.app/Contents/MacOS/soffice":
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", _patched_exists)


# A machine where every dependency, core and optional, resolves.
_ALL_PRESENT = {
    "pandoc": "/usr/bin/pandoc",
    "soffice": "/usr/bin/soffice",
    "node": "/usr/bin/node",
    "npx": "/usr/bin/npx",
    "mmdc": "/usr/local/bin/mmdc",
    "ollama": "/usr/bin/ollama",
}


class TestDiagnosis:
    """``run_checks`` maps a dependency environment to check + feature status."""

    def test_all_dependencies_present_is_fully_ok(self):
        """A complete toolchain reports every check OK and no core failure."""
        report = doctor.run_checks(which=fake_which(_ALL_PRESENT))
        # Every named check is green.
        assert report.get("Pandoc").status == doctor.STATUS_OK
        assert report.get("LibreOffice").status == doctor.STATUS_OK
        assert report.get("Node.js").status == doctor.STATUS_OK
        assert report.get("Mermaid CLI").status == doctor.STATUS_OK
        assert report.get("Ollama").status == doctor.STATUS_OK
        # Core is healthy and every feature is fully available.
        assert report.core_failing() is False
        assert report.feature_status("pdf") == doctor.STATUS_OK
        assert report.feature_status("mermaid") == doctor.STATUS_OK

    def test_missing_dependency_matrix(self):
        """Each missing tool drives the right check status and feature fallout.

        Sweeps: pandoc absent (core failure, all targets die), soffice absent
        (PDF partial, docx fine), Node absent (mermaid unavailable, INFO), and
        npx-without-global-mmdc (fine via lazy ``npx -y mmdc``). Each case is
        (present-tools, check, expected status, feature, feature status/None).
        """
        cases = [
            ({}, "Pandoc", doctor.STATUS_MISSING, "docx", "UNAVAILABLE"),
            ({"pandoc": "/usr/bin/pandoc"}, "LibreOffice", doctor.STATUS_MISSING, "pdf", "PARTIAL"),
            (
                {"pandoc": "/usr/bin/pandoc"},
                "Node.js",
                doctor.STATUS_INFO,
                "mermaid",
                "UNAVAILABLE",
            ),
            (
                {"pandoc": "/p", "node": "/n", "npx": "/x"},
                "Mermaid CLI",
                doctor.STATUS_INFO,
                "mermaid",
                None,
            ),
        ]
        for present, check, expected_status, feature, feature_status in cases:
            report = doctor.run_checks(which=fake_which(present))
            # The named check lands on its expected status …
            assert report.get(check).status == expected_status, check
            if feature_status is not None:
                # … and the derived feature availability matches.
                assert report.feature_status(feature) == feature_status, check

            # Case-specific extra guarantees that don't fit the shared columns.
            if check == "Pandoc":
                assert report.core_failing() is True
                assert report.feature_status("pptx") == "UNAVAILABLE"
                assert report.feature_status("pdf") == "UNAVAILABLE"
            else:
                assert report.core_failing() is False
            if check == "LibreOffice":
                assert report.feature_status("docx") == doctor.STATUS_OK
            if check == "Mermaid CLI":
                assert "npx" in report.get("Mermaid CLI").detail


class TestCli:
    """The ``main``/``render`` surface: JSON, human output, exit codes."""

    def test_core_only_install_json_and_exit(self, capsys):
        """A core-only install exits 0 in both plain and ``--json`` modes.

        Folds the "optional-missing → exit 0" contract together with the
        stable JSON shape, since both describe the same healthy-core report.

        Parameters
        ----------
        capsys : pytest.CaptureFixture
            Captures the JSON payload for shape assertions.
        """
        report = _make_report_only_pandoc()
        # Plain mode: optional gaps never fail the command.
        with patch.object(doctor, "run_checks", return_value=report):
            assert doctor.main([]) == 0
        capsys.readouterr()  # drop the plain-mode output before re-running

        # --json mode: same rc, plus a well-formed, documented payload shape.
        with patch.object(doctor, "run_checks", return_value=report):
            rc = doctor.main(["--json"])
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["core_failing"] is False
        assert "features" in payload and "pdf" in payload["features"]
        assert any(c["name"] == "Pandoc" for c in payload["checks"])

    def test_render_is_scannable_with_result_footer(self):
        """Human-readable output groups checks and ends with a Result footer."""
        report = doctor.run_checks(which=fake_which({"pandoc": "/p"}))
        text = doctor.render(report)
        # The rendered report carries every section header plus a summary.
        assert "Core:" in text
        assert "Optional:" in text
        assert "Templates:" in text
        assert "Result:" in text
        assert "DOCX export" in text and "PDF export" in text

    def test_pandoc_missing_returns_exit_1(self, capsys):
        """Core failure is the load-bearing contract: exit 1 and a loud MISSING.

        Kept standalone as the regression the CLI exists to guarantee — a
        broken core must be a non-zero exit so CI/scripts can gate on it.

        Parameters
        ----------
        capsys : pytest.CaptureFixture
            Captures the rendered report for the MISSING assertion.
        """
        with patch.object(doctor, "run_checks", return_value=_make_report_missing_pandoc()):
            rc = doctor.main([])
        # Non-zero exit + a visible MISSING marker for Pandoc.
        assert rc == 1
        out = capsys.readouterr().out
        assert "Pandoc" in out and "MISSING" in out


# ─────────────────────────────────────────────────────────────────────
# Helpers used by the patches above
# ─────────────────────────────────────────────────────────────────────


def _make_report_missing_pandoc() -> doctor.Report:
    """Build a minimal report whose only check is a missing Pandoc.

    Returns
    -------
    doctor.Report
        Report with a single ``STATUS_MISSING`` Pandoc entry.
    """
    r = doctor.Report()
    r.add("Pandoc", doctor.STATUS_MISSING, "fake — install pandoc")
    return r


def _make_report_only_pandoc() -> doctor.Report:
    """Build a report where core is healthy but LibreOffice is missing.

    Returns
    -------
    doctor.Report
        Report modelling a core-only install (optional deps absent).
    """
    r = doctor.Report()
    r.add("Python", doctor.STATUS_OK, "3.12.0")
    r.add("md2star", doctor.STATUS_OK, "test")
    r.add("Pandoc", doctor.STATUS_OK, "fake 3.x")
    r.add("LibreOffice", doctor.STATUS_MISSING, "", section="Optional")
    return r
