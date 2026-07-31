"""
Tests for md2star.reverse — the DOCX/PPTX/PDF → Markdown direction.

The pure logic (supported-extension gate, availability probe, error paths) runs
everywhere with no heavy dependency. The real extraction is exercised as a
round-trip (Markdown → DOCX → Markdown) and skipped cleanly when Pandoc or the
optional Kreuzberg engine is unavailable, matching tests/test_roundtrip_ocr.py.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

from md2star import reverse

_HAS_KREUZBERG = importlib.util.find_spec("kreuzberg") is not None
_HAS_PANDOC = shutil.which("pandoc") is not None


class TestPureLogic:
    """Extension gating, availability probe, and precise error paths."""

    def test_supported_extensions(self) -> None:
        assert reverse.is_supported("report.docx")
        assert reverse.is_supported("DECK.PPTX")  # case-insensitive
        assert reverse.is_supported("paper.pdf")
        assert not reverse.is_supported("notes.md")
        assert not reverse.is_supported("data.txt")

    def test_reverse_available_is_bool(self) -> None:
        # Whatever the environment, the probe must answer without importing the
        # heavy engine or raising.
        assert isinstance(reverse.reverse_available(), bool)

    def test_missing_file_raises_filenotfound(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            reverse.to_markdown(tmp_path / "nope.pdf")

    def test_unsupported_extension_raises_valueerror(self, tmp_path: Path) -> None:
        f = tmp_path / "notes.md"
        f.write_text("# hi", encoding="utf-8")
        with pytest.raises(ValueError, match="unsupported input"):
            reverse.to_markdown(f)

    def test_missing_kreuzberg_raises_reverse_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Simulate the base install (no [ocr] extra): the import inside
        # to_markdown must fail into a clear ReverseUnavailable with the hint.
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK\x03\x04dummy")  # a real (supported) extension, dummy bytes

        import builtins

        real_import = builtins.__import__

        def _fake_import(name: str, *args: object, **kwargs: object):
            if name == "kreuzberg" or name.startswith("kreuzberg."):
                raise ImportError("simulated missing kreuzberg")
            return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        with pytest.raises(reverse.ReverseUnavailable, match="md2star\\[ocr\\]"):
            reverse.to_markdown(f)


@pytest.mark.skipif(
    not (_HAS_PANDOC and _HAS_KREUZBERG),
    reason="round-trip needs pandoc (forward) + kreuzberg (reverse)",
)
class TestRoundTrip:
    """Markdown → DOCX → Markdown should recover the salient content."""

    def test_docx_roundtrip_recovers_text(self, tmp_path: Path) -> None:
        from md2star.cli import _convert

        src_md = tmp_path / "in.md"
        src_md.write_text("# Heading One\n\nA **bold** word and a list:\n\n- alpha\n- beta\n",
                          encoding="utf-8")
        docx = tmp_path / "out.docx"
        assert _convert("docx", [str(src_md), "-o", str(docx)]) == 0
        assert docx.is_file()

        md = reverse.to_markdown(docx)
        # Content, not byte-identity: extraction recovers the words + structure.
        assert "Heading One" in md
        assert "bold" in md
        assert "alpha" in md and "beta" in md
        assert md.endswith("\n")
