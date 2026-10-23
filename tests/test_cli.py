def test_converting_a_file_over_itself_is_refused(tmp_path) -> None:
    """The destination must not be the source.

    `md2docx doc.md -o doc.md` replaced a 37-byte Markdown file with a 16 kB
    DOCX and printed "Wrote: doc.md" as though that were a success: the
    document being converted is gone and nothing says so. Found by running the
    binary, not by reading it — the same sweep that turned up the identical
    fault in audio-helper and video-helper.

    Asserted on the bytes, not only on the exit code: a guard that refused
    *after* the write would satisfy an exit-code-only test.
    """
    import subprocess
    import sys

    source = tmp_path / "doc.md"
    source.write_text("# Titre\n\nUn paragraphe.\n", encoding="utf-8")
    before = source.read_bytes()

    for fmt in ("docx", "pptx"):
        for spelling in (str(source), f"./{source.name}"):
            done = subprocess.run(
                [sys.executable, "-m", "md2star.cli", fmt, str(source), "-o", spelling],
                capture_output=True,
                text=True,
                cwd=tmp_path,
            )
            assert done.returncode != 0, f"{fmt} {spelling} reported success"
            assert source.read_bytes() == before, f"{fmt} {spelling} overwrote its own source"


def test_the_ordinary_conversion_still_writes(tmp_path) -> None:
    """The guard must not cost the legitimate call."""
    import subprocess
    import sys

    source = tmp_path / "doc.md"
    source.write_text("# Titre\n\nUn paragraphe.\n", encoding="utf-8")
    target = tmp_path / "out.docx"
    done = subprocess.run(
        [sys.executable, "-m", "md2star.cli", "docx", str(source), "-o", str(target)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert done.returncode == 0, done.stderr[-400:]
    assert target.exists() and target.stat().st_size > 0
    assert source.read_text(encoding="utf-8").startswith("# Titre")
