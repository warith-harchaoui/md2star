"""
Every console script answers ``--help`` and returns, instead of serving.

``md2star-api`` and ``md2star-mcp`` read their bind from ``MD2STAR_HOST`` /
``MD2STAR_PORT`` and ignored their arguments, so ``md2star-mcp --help``
started a server on every interface and never returned.
Each script named in ``[project.scripts]`` now runs with ``--help`` under a
timeout and must print a click usage line. A script whose optional extra is not
installed is skipped, by name, rather than counted as a pass.

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# The module an entry point cannot even import without, keyed on the last
# component of its module path: the HTTP surface needs the [api] extra, the MCP
# surface the [mcp] extra on top.
_NEEDS = {"api": ("fastapi", "uvicorn"), "mcp": ("fastapi", "uvicorn", "fastapi_mcp")}


def _scripts() -> list[tuple[str, str, str]]:
    # Read rather than parsed: ``tomllib`` is 3.11+.
    manifest = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = manifest.split("[project.scripts]", 1)[1].split("\n[", 1)[0]
    return re.findall(r'^([\w-]+)\s*=\s*"([\w.]+):(\w+)"', block, re.M)


@pytest.mark.parametrize(("name", "module", "func"), _scripts())
def test_the_command_answers_help(name: str, module: str, func: str) -> None:
    missing = [
        m for m in _NEEDS.get(module.rsplit(".", 1)[-1], ()) if importlib.util.find_spec(m) is None
    ]
    if missing:
        pytest.skip(f"{name} needs {', '.join(missing)}, not installed here")
    code = f"import sys; from {module} import {func}; sys.argv[0] = {name!r}; {func}()"
    proc = subprocess.run(
        [sys.executable, "-c", code, "--help"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr[-800:]
    assert "Usage:" in proc.stdout, proc.stdout[:400]
