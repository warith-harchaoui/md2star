"""
test_json_to_bib.py — Unit tests for bib/json_to_bib.py.

Tests cover every public pure function in the module:
``coerce_int``, ``normalize_language``, ``sanitize_bibtex_key``,
``bibtex_escape``, ``infer_entry_type``, ``format_authors``,
``parse_resource``, ``resource_to_bibtex``, and ``resources_to_bibtex``.

The converter transforms deraison.ai resources.json into pandoc-friendly
BibTeX. Tests verify type coercion, emoji flag normalization, BibTeX
escaping, entry type inference, and full resource parsing/formatting.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ── Make the bib/ directory importable ────────────────────────────
_BIB_DIR = str(Path(__file__).resolve().parent.parent / "bib")
if _BIB_DIR not in sys.path:
    sys.path.insert(0, _BIB_DIR)

from json_to_bib import (  # noqa: E402
    Resource,
    bibtex_escape,
    coerce_int,
    format_authors,
    infer_entry_type,
    normalize_language,
    parse_resource,
    resource_to_bibtex,
    resources_to_bibtex,
    sanitize_bibtex_key,
)


# ──────────────────────────────────────────────────────────────────
# coerce_int
# ──────────────────────────────────────────────────────────────────


class TestCoerceInt:
    """Tests for coerce_int()."""

    def test_none(self) -> None:
        """None input should return None (no coercion attempted)."""
        assert coerce_int(None) is None

    def test_int(self) -> None:
        """Integer input should pass through unchanged."""
        assert coerce_int(42) == 42

    def test_str_valid(self) -> None:
        """Numeric string should be converted to int."""
        # Common case: JSON "year" field may be string or int
        assert coerce_int("2023") == 2023

    def test_str_empty(self) -> None:
        """Empty string should return None (not 0)."""
        assert coerce_int("") is None

    def test_str_spaces(self) -> None:
        """Whitespace-only string should return None."""
        assert coerce_int("  ") is None

    def test_str_invalid(self) -> None:
        """Non-numeric string should return None."""
        assert coerce_int("abc") is None

    def test_float(self) -> None:
        """Float input should return None (only int/str are handled)."""
        # Floats are not int or str — should return None
        assert coerce_int(3.14) is None


# ──────────────────────────────────────────────────────────────────
# normalize_language
# ──────────────────────────────────────────────────────────────────


class TestNormalizeLanguage:
    """Tests for normalize_language()."""

    def test_empty(self) -> None:
        """Empty string should return empty string."""
        assert normalize_language("") == ""

    def test_french_flag(self) -> None:
        """French flag emoji should normalize to ISO 639-1 'fr'."""
        assert normalize_language("🇫🇷") == "fr"

    def test_british_flag(self) -> None:
        """British flag emoji should normalize to ISO 639-1 'en'."""
        assert normalize_language("🇬🇧") == "en"

    def test_two_flags(self) -> None:
        """Multiple flags should produce comma-separated language codes."""
        # Common case: bilingual resources (e.g., "🇫🇷 🇬🇧" → "fr, en")
        result = normalize_language("🇫🇷 🇬🇧")
        assert "fr" in result
        assert "en" in result

    def test_plain_text_passthrough(self) -> None:
        """Non-emoji text should pass through cleaning."""
        # Fallback: if no emoji flags found, return cleaned text
        assert normalize_language("English") == "English"


# ──────────────────────────────────────────────────────────────────
# sanitize_bibtex_key
# ──────────────────────────────────────────────────────────────────


class TestSanitizeBibtexKey:
    """Tests for sanitize_bibtex_key()."""

    def test_spaces_replaced(self) -> None:
        """Whitespace should be replaced with underscores."""
        assert sanitize_bibtex_key("hello world") == "hello_world"

    def test_special_chars(self) -> None:
        """Invalid BibTeX key characters should be removed or replaced."""
        # BibTeX keys must be alphanumeric, underscore, colon, hyphen only
        result = sanitize_bibtex_key("test!@#")
        assert "!" not in result
        assert "@" not in result

    def test_empty(self) -> None:
        """Empty key should fall back to 'untitled'."""
        assert sanitize_bibtex_key("") == "untitled"

    def test_already_clean(self) -> None:
        """Valid keys should pass through unchanged."""
        assert sanitize_bibtex_key("clean_key-123") == "clean_key-123"


# ──────────────────────────────────────────────────────────────────
# bibtex_escape
# ──────────────────────────────────────────────────────────────────


class TestBibtexEscape:
    """Tests for bibtex_escape()."""

    def test_braces(self) -> None:
        """Braces must be escaped (they're BibTeX field delimiters)."""
        assert r"\{" in bibtex_escape("{")
        assert r"\}" in bibtex_escape("}")

    def test_percent(self) -> None:
        """Percent signs must be escaped (they start BibTeX comments)."""
        assert r"\%" in bibtex_escape("100%")

    def test_backslash(self) -> None:
        """Backslashes must be double-escaped."""
        # Backslash is the escape character, so it needs escaping itself
        result = bibtex_escape("a\\b")
        assert "\\\\" in result

    def test_plain_text(self) -> None:
        """Plain text without special characters should pass through."""
        assert bibtex_escape("hello") == "hello"


# ──────────────────────────────────────────────────────────────────
# infer_entry_type
# ──────────────────────────────────────────────────────────────────


class TestInferEntryType:
    """Tests for infer_entry_type()."""

    def test_book(self) -> None:
        """'Book' kind should map to BibTeX @book."""
        assert infer_entry_type("Book") == "book"

    def test_paper(self) -> None:
        """'Paper' kind should map to BibTeX @article."""
        assert infer_entry_type("Paper") == "article"

    def test_article(self) -> None:
        """'Article' kind should map to BibTeX @article."""
        assert infer_entry_type("Article") == "article"

    def test_conference(self) -> None:
        """'Conference' kind should map to BibTeX @inproceedings."""
        assert infer_entry_type("Conference") == "inproceedings"

    def test_misc(self) -> None:
        """Unknown kinds should default to BibTeX @misc."""
        # Conservative approach: unknown types become @misc
        assert infer_entry_type("Video") == "misc"

    def test_case_insensitive(self) -> None:
        """Kind matching should be case-insensitive."""
        assert infer_entry_type("BOOK") == "book"


# ──────────────────────────────────────────────────────────────────
# format_authors
# ──────────────────────────────────────────────────────────────────


class TestFormatAuthors:
    """Tests for format_authors()."""

    def test_single(self) -> None:
        """Single author should return the name without 'and'."""
        assert format_authors(["Alice"]) == "Alice"

    def test_multiple(self) -> None:
        """Multiple authors should be joined with ' and '."""
        # BibTeX format: "Author1 and Author2 and Author3"
        assert format_authors(["Alice", "Bob"]) == "Alice and Bob"

    def test_empty(self) -> None:
        """Empty author list should return empty string."""
        assert format_authors([]) == ""


# ──────────────────────────────────────────────────────────────────
# parse_resource
# ──────────────────────────────────────────────────────────────────


class TestParseResource:
    """Tests for parse_resource()."""

    def test_valid_dict(self) -> None:
        """Complete JSON object should parse into a Resource with all fields."""
        # Typical resource entry with all fields populated
        obj = {
            "id": "res_1",
            "title": "Test Book",
            "link": "https://example.com",
            "authors": ["Alice"],
            "year": 2020,
            "kind": "Book",
            "language": "🇬🇧",
        }
        res = parse_resource(obj)
        assert res.rid == "res_1"
        assert res.title == "Test Book"
        assert res.url == "https://example.com"
        assert res.authors == ["Alice"]
        assert res.year == 2020
        assert res.kind == "Book"
        # Language emoji should be normalized to ISO code
        assert res.language == "en"

    def test_missing_optional_fields(self) -> None:
        """A minimal entry with only 'id' should still parse."""
        obj = {"id": "minimal"}
        res = parse_resource(obj)
        assert res.rid == "minimal"
        assert res.title == ""
        assert res.authors == []
        assert res.year is None

    def test_authors_as_string(self) -> None:
        """If 'authors' is a single string instead of a list, wrap it."""
        obj = {"id": "x", "authors": "Solo Author"}
        res = parse_resource(obj)
        assert res.authors == ["Solo Author"]


# ──────────────────────────────────────────────────────────────────
# resource_to_bibtex
# ──────────────────────────────────────────────────────────────────


class TestResourceToBibtex:
    """Tests for resource_to_bibtex()."""

    def test_basic_output(self) -> None:
        """Complete resource should produce valid BibTeX with all fields."""
        res = Resource(
            rid="test_1",
            title="My Title",
            url="https://example.com",
            authors=["Alice"],
            year=2021,
            kind="Book",
            language="en",
        )
        bib = resource_to_bibtex(res, add_urldate=False, urldate="2025-01-01")
        # Verify entry type inference (Book → @book)
        assert "@book{test_1," in bib
        # Verify all fields are present and escaped
        assert "title = {My Title}" in bib
        assert "author = {Alice}" in bib
        assert "year = {2021}" in bib
        assert "url = {https://example.com}" in bib
        # urldate should NOT be present when add_urldate=False
        assert "urldate" not in bib

    def test_with_urldate(self) -> None:
        """When add_urldate=True, urldate field should be included."""
        # urldate is useful for CSL styles that display access dates
        res = Resource(
            rid="t",
            title="T",
            url="https://x.com",
            authors=[],
            year=None,
            kind="Misc",
            language="",
        )
        bib = resource_to_bibtex(res, add_urldate=True, urldate="2025-06-15")
        assert "urldate = {2025-06-15}" in bib


# ──────────────────────────────────────────────────────────────────
# resources_to_bibtex
# ──────────────────────────────────────────────────────────────────


class TestResourcesToBibtex:
    """Tests for resources_to_bibtex()."""

    def test_multiple_resources(self) -> None:
        """Multiple resources should produce multiple BibTeX entries."""
        # Each resource becomes a separate @entry{key, ...} block
        r1 = Resource("a", "A", "", [], None, "Misc", "")
        r2 = Resource("b", "B", "", [], None, "Misc", "")
        bib = resources_to_bibtex([r1, r2], add_urldate=False)
        assert "@misc{a," in bib
        assert "@misc{b," in bib

    def test_empty_iterable(self) -> None:
        """Empty resource list should produce empty BibTeX (whitespace only)."""
        bib = resources_to_bibtex([], add_urldate=False)
        assert bib.strip() == ""
