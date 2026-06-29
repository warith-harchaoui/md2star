"""md2star doctor — environment diagnostics.

Two layers, separated on purpose:

1. **Pure logic** (``run_checks``): walks the dependency list, calls
   ``shutil.which`` / ``subprocess.run`` / filesystem probes, returns a
   structured :class:`Report` dataclass. No printing, no ``sys.exit``,
   no colour — easy to unit-test via ``monkeypatch``.

2. **CLI renderer** (``main``): formats a :class:`Report` for a terminal,
   prints to stdout, and picks an exit code. Exits ``0`` unless a
   *core* dependency (Python interpreter, ``md2star`` package,
   ``pandoc``) is broken; optional missing pieces produce ``WARNING``
   / ``INFO`` lines but do not fail the command.

The output is deliberately scannable: one line per check, status in a
fixed-width column on the left, resolved path / version on the right.
A "Result" footer summarises which conversion targets actually work in
this environment so a returning user can see at a glance whether they
need to install anything before reaching for ``md2docx``.


Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from . import __version__
from .cache import cache_dir

# ─────────────────────────────────────────────────────────────────────
# Status taxonomy
# ─────────────────────────────────────────────────────────────────────


# Status strings are intentionally short fixed-width tokens so terminal
# output aligns into columns without ANSI escapes (which trip up
# pipelines / CI logs / non-tty consumers).
STATUS_OK      = "OK"
STATUS_WARNING = "WARNING"
STATUS_MISSING = "MISSING"
STATUS_INFO    = "INFO"
STATUS_ERROR   = "ERROR"

# Severity ranks the statuses for the "are we healthy?" rollup.
# Anything > _RANK[STATUS_WARNING] in a *core* check fails the run.
_RANK = {
    STATUS_OK:      0,
    STATUS_INFO:    0,
    STATUS_WARNING: 1,
    STATUS_MISSING: 2,
    STATUS_ERROR:   3,
}


@dataclass
class Check:
    """One row in the doctor's report."""

    name: str
    status: str
    detail: str = ""
    section: str = "Core"


@dataclass
class Report:
    """Structured doctor output. The CLI prints it; tests assert on it."""

    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "", section: str = "Core") -> None:
        self.checks.append(Check(name=name, status=status, detail=detail, section=section))

    def get(self, name: str) -> Check | None:
        for c in self.checks:
            if c.name == name:
                return c
        return None

    def core_failing(self) -> bool:
        """True iff any check in the ``Core`` section is worse than WARNING."""
        return any(
            c.section == "Core" and _RANK.get(c.status, 0) >= _RANK[STATUS_MISSING]
            for c in self.checks
        )

    def feature_status(self, fmt: str) -> str:
        """Return ``OK`` / ``PARTIAL`` / ``UNAVAILABLE`` for a conversion target.

        ``docx``    — needs pandoc.
        ``pptx``    — needs pandoc.
        ``pdf``     — needs pandoc + soffice.
        ``mermaid`` — needs node + (mermaid-cli or npx).
        """
        def ok(name: str) -> bool:
            c = self.get(name)
            return c is not None and c.status == STATUS_OK

        if fmt == "docx" or fmt == "pptx":
            return STATUS_OK if ok("Pandoc") else "UNAVAILABLE"
        if fmt == "pdf":
            if ok("Pandoc") and ok("LibreOffice"):
                return STATUS_OK
            if ok("Pandoc"):
                return "PARTIAL"
            return "UNAVAILABLE"
        if fmt == "mermaid":
            return STATUS_OK if ok("Node.js") else "UNAVAILABLE"
        return "UNAVAILABLE"


# ─────────────────────────────────────────────────────────────────────
# Individual checks — pure, mockable via the injected helpers
# ─────────────────────────────────────────────────────────────────────


def _run_version(cmd: list[str], timeout: float = 5.0,
                 runner: Callable[..., subprocess.CompletedProcess[str]] | None = None
                 ) -> str | None:
    """Return the first line of ``<cmd> --version`` stdout, or None on failure."""
    runner = runner or (lambda *a, **kw: subprocess.run(*a, **kw))
    try:
        proc = runner(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    out = (proc.stdout or proc.stderr or "").strip()
    return out.splitlines()[0] if out else None


def _check_pandoc(report: Report, which: Callable[[str], str | None]) -> None:
    path = which("pandoc")
    if path is None:
        report.add(
            "Pandoc", STATUS_MISSING,
            "Install: https://pandoc.org/installing.html",
        )
        return
    version = _run_version([path, "--version"]) or "(unknown version)"
    report.add("Pandoc", STATUS_OK, f"{version} — {path}")


def _check_libreoffice(report: Report, which: Callable[[str], str | None]) -> None:
    candidates = [
        which("soffice"),
        which("libreoffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice"
            if Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").exists()
            else None,
    ]
    path = next((p for p in candidates if p), None)
    if path is None:
        report.add(
            "LibreOffice", STATUS_MISSING,
            "Needed for md2pdf and the GUI's PDF preview. "
            "Install: brew install --cask libreoffice / apt install libreoffice",
            section="Optional",
        )
        return
    version = _run_version([path, "--version"], timeout=10.0) or "(unknown version)"
    report.add("LibreOffice", STATUS_OK, f"{version} — {path}", section="Optional")


def _check_node(report: Report, which: Callable[[str], str | None]) -> None:
    path = which("node")
    if path is None:
        report.add(
            "Node.js", STATUS_INFO,
            "Optional — needed only for ``` ```mermaid ``` ``` blocks. "
            "Install: https://nodejs.org/",
            section="Optional",
        )
        return
    version = _run_version([path, "--version"]) or "(unknown)"
    report.add("Node.js", STATUS_OK, f"{version} — {path}", section="Optional")


def _check_mermaid_cli(report: Report, which: Callable[[str], str | None]) -> None:
    # md2star uses `npx -y @mermaid-js/mermaid-cli` on demand, so the
    # absence of a globally-installed `mmdc` is fine when `npx` is
    # present. We report both states for transparency.
    mmdc = which("mmdc")
    npx = which("npx")
    if mmdc is not None:
        version = _run_version([mmdc, "--version"]) or "(unknown)"
        report.add(
            "Mermaid CLI", STATUS_OK,
            f"{version} (global mmdc) — {mmdc}",
            section="Optional",
        )
        return
    if npx is not None:
        report.add(
            "Mermaid CLI", STATUS_INFO,
            "No global mmdc; ``npx @mermaid-js/mermaid-cli`` will be used on demand.",
            section="Optional",
        )
        return
    report.add(
        "Mermaid CLI", STATUS_INFO,
        "Optional — no Node.js, so mermaid blocks are skipped (kept as code fences).",
        section="Optional",
    )


def _check_ollama(report: Report, which: Callable[[str], str | None]) -> None:
    path = which("ollama")
    if path is None:
        report.add(
            "Ollama", STATUS_INFO,
            "Optional — needed only for the --lint LLM auto-fix pass.",
            section="Optional",
        )
        return
    version = _run_version([path, "--version"]) or "(unknown)"
    report.add("Ollama", STATUS_OK, f"{version} — {path}", section="Optional")


def _check_templates(report: Report) -> None:
    try:
        docx = resources.files("md2star.data").joinpath("template.docx")
        pptx = resources.files("md2star.data").joinpath("template.pptx")
        if docx.is_file() and pptx.is_file():
            report.add(
                "Bundled templates", STATUS_OK,
                "template.docx + template.pptx — md2star/data/",
                section="Templates",
            )
            return
    except (FileNotFoundError, ModuleNotFoundError, OSError):
        pass
    report.add(
        "Bundled templates", STATUS_ERROR,
        "template.docx and/or template.pptx missing from the installed wheel — reinstall md2star.",
        section="Templates",
    )


def _check_cache(report: Report) -> None:
    try:
        root = cache_dir()
        # Probe writability without actually leaving a file behind.
        probe = root / ".doctor-probe"
        probe.touch()
        probe.unlink()
        report.add(
            "Cache directory", STATUS_OK, str(root), section="Templates",
        )
    except OSError as exc:
        report.add(
            "Cache directory", STATUS_WARNING,
            f"Not writable ({exc}); md2star will fall back to /tmp.",
            section="Templates",
        )


def _check_python(report: Report) -> None:
    v = sys.version_info
    detail = f"{v.major}.{v.minor}.{v.micro} — {sys.executable}"
    if (v.major, v.minor) < (3, 10):
        report.add(
            "Python", STATUS_ERROR,
            f"{detail} — md2star requires Python ≥ 3.10.",
        )
        return
    report.add("Python", STATUS_OK, detail)


def _check_md2star(report: Report) -> None:
    report.add("md2star", STATUS_OK, f"{__version__}")


def _check_platform(report: Report) -> None:
    report.add(
        "Platform", STATUS_INFO,
        f"{platform.system()} {platform.release()} ({platform.machine()})",
        section="Optional",
    )


# ─────────────────────────────────────────────────────────────────────
# Top-level orchestration
# ─────────────────────────────────────────────────────────────────────


def run_checks(
    which: Callable[[str], str | None] | None = None,
) -> Report:
    """Walk every check and return a :class:`Report`.

    *which* defaults to :func:`shutil.which`; tests inject a fake to
    simulate "pandoc missing" / "soffice present" combinations without
    touching the real PATH.
    """
    which = which or shutil.which
    report = Report()
    _check_python(report)
    _check_md2star(report)
    _check_pandoc(report, which)
    _check_libreoffice(report, which)
    _check_node(report, which)
    _check_mermaid_cli(report, which)
    _check_ollama(report, which)
    _check_templates(report)
    _check_cache(report)
    _check_platform(report)
    return report


# ─────────────────────────────────────────────────────────────────────
# CLI rendering
# ─────────────────────────────────────────────────────────────────────


def render(report: Report) -> str:
    """Format *report* as a human-readable multi-section string."""
    out: list[str] = []
    out.append("md2star doctor")
    out.append("")

    # Group by section, preserving insertion order so the user reads
    # Core → Optional → Templates top to bottom.
    sections: dict[str, list[Check]] = {}
    for c in report.checks:
        sections.setdefault(c.section, []).append(c)

    for section, rows in sections.items():
        out.append(f"{section}:")
        width = max((len(r.name) for r in rows), default=10)
        for r in rows:
            label = r.name.ljust(width)
            tail = f" — {r.detail}" if r.detail else ""
            out.append(f"  {label}  {r.status:7}{tail}")
        out.append("")

    out.append("Result:")
    targets = [
        ("DOCX export",      report.feature_status("docx")),
        ("PPTX export",      report.feature_status("pptx")),
        ("PDF export",       report.feature_status("pdf")),
        ("Mermaid diagrams", report.feature_status("mermaid")),
    ]
    width = max(len(name) for name, _ in targets)
    for name, status in targets:
        out.append(f"  {name.ljust(width)}  {status}")

    if report.core_failing():
        out.append("")
        out.append(
            "✗ Core dependencies are broken — fix the items above before running md2star."
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    """Console entry point: ``md2star doctor``."""
    parser = argparse.ArgumentParser(
        prog="md2star doctor",
        description="Print a diagnostic summary of the environment md2star runs in.",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit the report as JSON instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    report = run_checks()

    if args.json:
        import json
        payload = {
            "checks": [
                {"name": c.name, "status": c.status,
                 "detail": c.detail, "section": c.section}
                for c in report.checks
            ],
            "features": {
                fmt: report.feature_status(fmt)
                for fmt in ("docx", "pptx", "pdf", "mermaid")
            },
            "core_failing": report.core_failing(),
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render(report))

    return 1 if report.core_failing() else 0


if __name__ == "__main__":
    sys.exit(main())
