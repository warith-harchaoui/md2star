"""The ``--skip-phase`` help names every phase the pipeline knows.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

from click.testing import CliRunner

from md2star.cli import cli
from md2star.preprocessing.pipeline import PHASES


def test_the_skip_phase_help_names_every_phase() -> None:
    """A phase missing from the help is a phase nobody learns they can skip."""
    result = CliRunner().invoke(cli, ["docx", "--help"], terminal_width=10_000)
    assert result.exit_code == 0, result.output
    missing = sorted(p for p in PHASES if p not in result.output)
    assert not missing, f"--skip-phase help omits {missing}"
