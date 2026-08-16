"""md2star doctor, environment diagnostics.

Two layers, separated on purpose:

1. **Pure logic** (``run_checks``): walks the dependency list, calls
   ``shutil.which`` / ``subprocess.run`` / filesystem probes, returns a
   structured :class:`Report` dataclass. No printing, no ``sys.exit``,
   no colour, easy to unit-test via ``monkeypatch``.

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
        """Append one :class:`Check` row to the report.

        Parameters
        ----------
        name : str
            Human label shown in the leftmost report column.
        status : str
            One of the ``STATUS_*`` tokens (``OK`` / ``WARNING`` / …).
        detail : str, optional
            Free-form right-column text (version, path, or install hint).
        section : str, optional
            Display group (``Core`` / ``Optional`` / ``Templates``).

        Returns
        -------
        None
        """
        # Rows are stored in call order; render() re-groups them by section.
        self.checks.append(Check(name=name, status=status, detail=detail, section=section))

    def get(self, name: str) -> Check | None:
        """Return the first check matching *name*, or ``None`` if absent.

        Parameters
        ----------
        name : str
            The :attr:`Check.name` to look up.

        Returns
        -------
        Check | None
            The matching row, or ``None`` when no check carries that name.
        """
        # Linear scan is fine: the report holds a dozen rows at most.
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
            """Report whether the named check exists and passed.

            Parameters
            ----------
            name : str
                The :attr:`Check.name` whose status we probe.

            Returns
            -------
            bool
                ``True`` only when a check with that name is present *and*
                its status is exactly ``STATUS_OK``.
            """
            # A missing check counts as "not ok" so absence and failure are
            # treated identically when deciding feature readiness.
            c = self.get(name)
            return c is not None and c.status == STATUS_OK

        # Office formats need only pandoc — a single binary gates both.
        if fmt == "docx" or fmt == "pptx":
            return STATUS_OK if ok("Pandoc") else "UNAVAILABLE"
        # PDF is a two-stage pipeline (pandoc → soffice), hence three outcomes:
        # both present is OK, pandoc-only is PARTIAL (docx works, PDF doesn't),
        # neither is fully UNAVAILABLE.
        if fmt == "pdf":
            if ok("Pandoc") and ok("LibreOffice"):
                return STATUS_OK
            if ok("Pandoc"):
                return "PARTIAL"
            return "UNAVAILABLE"
        # Mermaid keys off Node (npx pulls the CLI on demand), not a global mmdc.
        if fmt == "mermaid":
            return STATUS_OK if ok("Node.js") else "UNAVAILABLE"
        # Unknown format name: fail closed rather than claim support.
        return "UNAVAILABLE"


# ─────────────────────────────────────────────────────────────────────
# Individual checks — pure, mockable via the injected helpers
# ─────────────────────────────────────────────────────────────────────


def _run_version(cmd: list[str], timeout: float = 5.0,
                 runner: Callable[..., subprocess.CompletedProcess[str]] | None = None
                 ) -> str | None:
    """Return the first line of ``<cmd> --version`` stdout, or None on failure."""
    # Default to the real subprocess.run; tests inject a fake to avoid shelling
    # out and to simulate timeouts / missing binaries deterministically.
    runner = runner or (lambda *a, **kw: subprocess.run(*a, **kw))
    try:
        # check=False: a non-zero exit is not an error here — some tools print
        # their version to stderr and exit 1, and we still want that text.
        proc = runner(
            cmd, capture_output=True, text=True, timeout=timeout, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # Any spawn/timeout failure means "no usable version" — caller
        # substitutes a placeholder rather than propagating the exception.
        return None
    # Prefer stdout, but fall back to stderr for tools that report there; only
    # the first line is the version banner, so drop the rest (help/notices).
    out = (proc.stdout or proc.stderr or "").strip()
    return out.splitlines()[0] if out else None


def _check_pandoc(report: Report, which: Callable[[str], str | None]) -> None:
    """Check for pandoc — the one hard dependency (Core section)."""
    path = which("pandoc")
    # Pandoc is CORE: without it nothing converts, so a miss is MISSING in the
    # default Core section, which flips ``core_failing()`` and fails doctor.
    if path is None:
        report.add(
            "Pandoc", STATUS_MISSING,
            "Install: https://pandoc.org/installing.html",
        )
        return
    # Present → record the version + resolved path for the report.
    version = _run_version([path, "--version"]) or "(unknown version)"
    report.add("Pandoc", STATUS_OK, f"{version} — {path}")


def _check_libreoffice(report: Report, which: Callable[[str], str | None]) -> None:
    """Check for LibreOffice — needed only for PDF (Optional section)."""
    # Try the two PATH names plus the macOS .app location that isn't on PATH.
    candidates = [
        which("soffice"),
        which("libreoffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice"
            if Path("/Applications/LibreOffice.app/Contents/MacOS/soffice").exists()
            else None,
    ]
    # First hit wins; None means "not found anywhere".
    path = next((p for p in candidates if p), None)
    # Optional section: a miss degrades PDF to PARTIAL but never fails doctor.
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
    """Check for Node.js — needed only for mermaid rendering (Optional)."""
    path = which("node")
    # INFO (not MISSING): mermaid is a niche feature, so absence is informational
    # rather than a warning — we don't want to alarm users who never use it.
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
    """Check for the Mermaid CLI — needed only for diagram rendering (Optional).

    Parameters
    ----------
    report : Report
        The report to append the ``Mermaid CLI`` row to.
    which : Callable[[str], str | None]
        PATH resolver (injected so tests can fake ``mmdc`` / ``npx`` presence).

    Returns
    -------
    None
    """
    # md2star uses `npx -y @mermaid-js/mermaid-cli` on demand, so the
    # absence of a globally-installed `mmdc` is fine when `npx` is
    # present. We report both states for transparency.
    mmdc = which("mmdc")
    npx = which("npx")
    # Best case: a global mmdc is on PATH — record its version + path as OK.
    if mmdc is not None:
        version = _run_version([mmdc, "--version"]) or "(unknown)"
        report.add(
            "Mermaid CLI", STATUS_OK,
            f"{version} (global mmdc) — {mmdc}",
            section="Optional",
        )
        return
    # No global binary, but npx can fetch it lazily — INFO, not a warning,
    # because diagrams will still render (just with a first-run download).
    if npx is not None:
        report.add(
            "Mermaid CLI", STATUS_INFO,
            "No global mmdc; ``npx @mermaid-js/mermaid-cli`` will be used on demand.",
            section="Optional",
        )
        return
    # Neither mmdc nor npx: without Node the feature is unavailable, but mermaid
    # blocks degrade gracefully to plain code fences, so this stays INFO.
    report.add(
        "Mermaid CLI", STATUS_INFO,
        "Optional — no Node.js, so mermaid blocks are skipped (kept as code fences).",
        section="Optional",
    )


def _check_ollama(report: Report, which: Callable[[str], str | None]) -> None:
    """Check for Ollama — needed only for the --lint LLM pass (Optional)."""
    path = which("ollama")
    # INFO for the same reason as Node: --lint is strictly opt-in.
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
    """Verify the wheel actually shipped its bundled templates."""
    # The two templates are packaged data; both must be present for the
    # offline-default styling to work.
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
    # Reaching here means the packaged data is missing — a corrupt/partial
    # install, hence ERROR (not just a warning): reinstalling is the fix.
    report.add(
        "Bundled templates", STATUS_ERROR,
        "template.docx and/or template.pptx missing from the installed wheel — reinstall md2star.",
        section="Templates",
    )


def _check_cache(report: Report) -> None:
    """Confirm the on-disk cache directory exists and is writable (Templates).

    Parameters
    ----------
    report : Report
        The report to append the ``Cache directory`` row to.

    Returns
    -------
    None
    """
    try:
        root = cache_dir()
        # Probe writability without actually leaving a file behind: touch then
        # immediately unlink, so a read-only mount surfaces as an OSError below.
        probe = root / ".doctor-probe"
        probe.touch()
        probe.unlink()
        report.add(
            "Cache directory", STATUS_OK, str(root), section="Templates",
        )
    except OSError as exc:
        # Not fatal — md2star transparently falls back to /tmp — so WARNING,
        # not ERROR; we just want the user to know caching is degraded.
        report.add(
            "Cache directory", STATUS_WARNING,
            f"Not writable ({exc}); md2star will fall back to /tmp.",
            section="Templates",
        )


def _check_python(report: Report) -> None:
    """Confirm the interpreter meets md2star's minimum version."""
    v = sys.version_info
    detail = f"{v.major}.{v.minor}.{v.micro} — {sys.executable}"
    # 3.10 is our floor (match/case, PEP 604 unions used throughout). Running
    # under an older interpreter is an ERROR, not a warning — features will
    # genuinely be broken.
    if (v.major, v.minor) < (3, 10):
        report.add(
            "Python", STATUS_ERROR,
            f"{detail} — md2star requires Python ≥ 3.10.",
        )
        return
    report.add("Python", STATUS_OK, detail)


def _check_md2star(report: Report) -> None:
    """Record md2star's own version so bug reports pin an exact build."""
    report.add("md2star", STATUS_OK, f"{__version__}")


def _check_platform(report: Report) -> None:
    """Record the host OS / release / arch for context in bug reports (Optional).

    Parameters
    ----------
    report : Report
        The report to append the ``Platform`` row to.

    Returns
    -------
    None
    """
    # Purely informational: never fails, but pins the exact OS/arch so
    # architecture-specific issues are diagnosable from a pasted report.
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
    # Order matters only for display grouping (render() re-groups by section),
    # but we run environment → core tools → optional tools → packaging so the
    # report reads roughly most-fundamental first.
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
        # Pad names to the longest in THIS section so status columns line up.
        width = max((len(r.name) for r in rows), default=10)
        for r in rows:
            label = r.name.ljust(width)
            # Only append the detail dash when there is a detail to show, so
            # bare rows don't end in a dangling separator.
            tail = f" — {r.detail}" if r.detail else ""
            out.append(f"  {label}  {r.status:7}{tail}")
        out.append("")

    # Bottom rollup: translate the raw checks into per-format readiness, which
    # is what the user actually cares about ("can I make a PDF?").
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

    # Only surface the loud failure banner when a Core check is broken; optional
    # gaps already read as WARNING/INFO above and must not trigger it.
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

    # Run the pure-logic layer once; both output modes render the same Report.
    report = run_checks()

    if args.json:
        # json is imported lazily: the common text path never pays for it.
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

    # Exit non-zero only for Core breakage so scripts can gate on md2star being
    # usable while tolerating missing optional tools.
    return 1 if report.core_failing() else 0


if __name__ == "__main__":
    sys.exit(main())
