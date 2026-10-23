"""Converting a file over its own source.

``md2docx doc.md -o doc.md`` replaced a 37-byte Markdown file with a 16 kB DOCX
and printed ``Wrote: doc.md`` as though that were a success: the document being
converted is gone and nothing says so. All three formats did it — docx, pptx,
pdf — and it was found by running the binary rather than by reading it, in the
same sweep that turned up the identical hole in audio-helper and video-helper.

Both tests drive :func:`md2star.cli.main` **in-process**. The first version
spawned ``sys.executable -m md2star.cli`` and turned the `coverage` job red:
pytest-cov instruments a Python child, that child writes a parallel data file
without branch coverage, and combining it with the parent's branch data is a
hard ``coverage.exceptions.DataError``. The sibling suites here spawn *pandoc*,
a non-Python binary coverage never hooks, which is why none of them hit it.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

from pathlib import Path

from md2star.cli import main

_SOURCE = "# Titre\n\nUn paragraphe.\n"


def test_converting_a_file_over_itself_is_refused(tmp_path: Path) -> None:
    """Four spellings of the same mistake, each asserted on the bytes.

    The assertion reads the file's contents and not only the exit code: a guard
    that refused *after* the write would satisfy an exit-code-only test, and
    write-then-fail is exactly what the original did.
    """
    source = tmp_path / "doc.md"
    source.write_text(_SOURCE, encoding="utf-8")
    before = source.read_bytes()
    # The same file by another name, built from the directory rather than by
    # chdir-ing into it. `monkeypatch.chdir` moved the process somewhere
    # `pyproject.toml` is not, so any Python child started from there read no
    # `[tool.coverage.run] branch = true` and wrote a branch-less data file
    # that the `coverage` job then refused to combine.
    dotted = str(tmp_path / "." / "doc.md")

    for fmt in ("docx", "pptx"):
        # The absolute path and the relative one name the same file; comparing
        # strings rather than resolved paths would catch only the first.
        for spelling in (str(source), dotted):
            assert main([fmt, str(source), "-o", spelling]) != 0, (
                f"{fmt} {spelling} reported success"
            )
            assert source.read_bytes() == before, f"{fmt} {spelling} overwrote its own source"


def test_the_ordinary_conversion_still_writes(tmp_path: Path) -> None:
    """The guard must not cost the legitimate call, which is the common one."""
    source = tmp_path / "doc.md"
    source.write_text(_SOURCE, encoding="utf-8")
    target = tmp_path / "out.docx"

    assert main(["docx", str(source), "-o", str(target)]) == 0
    assert target.exists() and target.stat().st_size > 0
    assert source.read_text(encoding="utf-8").startswith("# Titre")
