"""
test_preprocessing.py — Unit tests for scripts/preprocessing.py.

Tests for the ``preprocess_markdown`` function, which ensures that
every Markdown list item is preceded by a blank line. This preprocessing
step fixes common Markdown authoring issues where lists are "glued" to
preceding paragraphs, which Pandoc sometimes renders incorrectly.

Test Coverage:
- Edge cases: empty strings, whitespace-only, no lists
- Unordered lists: dash (-), asterisk (*), plus (+) markers
- Ordered lists: numbered items (1., 2., …)
- Nested lists: indented sub-items
- Code block preservation: list-like syntax inside fenced code blocks
- Mixed content: headings, paragraphs, lists, code blocks together
"""

from __future__ import annotations

import sys
from pathlib import Path

from unittest.mock import patch

import pytest

# ── Make the scripts/ directory importable ────────────────────────
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from preprocessing import preprocess_markdown  # noqa: E402


# ──────────────────────────────────────────────────────────────────
# Basic / edge-case tests
# ──────────────────────────────────────────────────────────────────


class TestPreprocessMarkdownBasic:
    """Tests for trivial and edge-case inputs."""

    def test_empty_string(self) -> None:
        """Empty input should return an empty string."""
        # Edge case: function must handle empty input gracefully
        assert preprocess_markdown("") == ""

    def test_no_lists(self) -> None:
        """Content without any list items should pass through unchanged."""
        # No list markers present → no transformations should occur
        text = "Hello\nworld\n\nParagraph two."
        assert preprocess_markdown(text) == text

    def test_blank_lines_only(self) -> None:
        """A string of blank lines should pass through unchanged."""
        # Edge case: only whitespace, no actual content
        text = "\n\n\n"
        assert preprocess_markdown(text) == text


# ──────────────────────────────────────────────────────────────────
# Unordered list tests
# ──────────────────────────────────────────────────────────────────


class TestUnorderedLists:
    """Tests for dash, star, and plus-style list markers."""

    def test_blank_line_inserted_before_dash_item(self) -> None:
        """A blank line should be inserted when text precedes a dash list."""
        # Common case: paragraph followed by list needs spacing for Pandoc
        result = preprocess_markdown("Hello\n- item")
        assert result == "Hello\n\n- item"

    def test_blank_line_inserted_before_star_item(self) -> None:
        """Works with asterisk markers too."""
        # Markdown supports multiple unordered list markers
        result = preprocess_markdown("Hello\n* item")
        assert result == "Hello\n\n* item"

    def test_blank_line_inserted_before_plus_item(self) -> None:
        """Works with plus markers too."""
        # Plus (+) is another valid unordered list marker
        result = preprocess_markdown("Hello\n+ item")
        assert result == "Hello\n\n+ item"

    def test_no_double_blank_line(self) -> None:
        """If a blank line already precedes a list item, no extra is added."""
        # Idempotency: don't add blank lines if one already exists
        text = "Hello\n\n- item"
        assert preprocess_markdown(text) == text

    def test_consecutive_items_get_blank_lines(self) -> None:
        """Each consecutive list item should be separated by a blank line."""
        # Converts "tight" lists to "loose" lists for better DOCX/PPTX spacing
        result = preprocess_markdown("- a\n- b\n- c")
        assert result == "- a\n\n- b\n\n- c"


# ──────────────────────────────────────────────────────────────────
# Ordered list tests
# ──────────────────────────────────────────────────────────────────


class TestOrderedLists:
    """Tests for numbered list markers (1., 2., …)."""

    def test_ordered_list_item(self) -> None:
        """Numbered list items should also get blank lines inserted."""
        # Ordered lists use the same spacing logic as unordered lists
        result = preprocess_markdown("Intro\n1. First\n2. Second")
        assert result == "Intro\n\n1. First\n\n2. Second"

    def test_multi_digit_numbers(self) -> None:
        """Multi-digit numbers (10., 100., …) should still be matched."""
        # Regex must handle numbers > 9 correctly
        result = preprocess_markdown("Intro\n10. Tenth")
        assert result == "Intro\n\n10. Tenth"


# ──────────────────────────────────────────────────────────────────
# Nested list tests
# ──────────────────────────────────────────────────────────────────


class TestNestedLists:
    """Tests for indented (nested) list items."""

    def test_nested_list_items(self) -> None:
        """Indented sub-items should also be separated by blank lines."""
        # Nested lists preserve indentation while adding spacing
        result = preprocess_markdown("- parent\n  - child")
        assert result == "- parent\n\n  - child"


# ──────────────────────────────────────────────────────────────────
# Code-block preservation tests
# ──────────────────────────────────────────────────────────────────


class TestCodeBlocks:
    """List-like syntax inside fenced code blocks must NOT be altered."""

    def test_code_block_preserved(self) -> None:
        """Lines inside ``` … ``` should not trigger blank-line injection."""
        # Critical: code examples often contain list-like syntax that must not be altered
        text = "```\n- not a list\n```"
        assert preprocess_markdown(text) == text

    def test_code_block_with_surrounding_text(self) -> None:
        """Code block between paragraphs: only real lists get spacing."""
        # Mixed content: code block contains list-like syntax, followed by a real list
        text = "Before\n```\n- code\n```\nAfter\n- real list"
        result = preprocess_markdown(text)
        # The "- code" inside the fence should be untouched (code preservation)
        assert "```\n- code\n```" in result
        # The real list item after the fence should get a blank line (list formatting)
        assert "After\n\n- real list" in result


# ──────────────────────────────────────────────────────────────────
# Mixed content tests
# ──────────────────────────────────────────────────────────────────


class TestMixedContent:
    """Tests combining headings, paragraphs, lists, and code blocks."""

    def test_heading_then_list(self) -> None:
        """A heading followed by a list should get a blank line."""
        # Headings are treated like paragraphs: need spacing before lists
        result = preprocess_markdown("## Heading\n- item")
        assert result == "## Heading\n\n- item"

    def test_paragraph_list_paragraph(self) -> None:
        """Paragraph → list → paragraph round-trip."""
        # Complex scenario: multiple list items between paragraphs
        text = "Intro\n- a\n- b\nOutro"
        result = preprocess_markdown(text)
        assert "Intro\n\n- a\n\n- b\nOutro" == result


# ──────────────────────────────────────────────────────────────────
# Mermaid Block tests
# ──────────────────────────────────────────────────────────────────


class TestMermaidBlocks:
    """Tests evaluating Mermaid to Kroki pipeline substitution."""

    @patch("preprocessing.fetch_kroki_mermaid")
    def test_mermaid_renders_success(self, mock_fetch) -> None:
        """A valid mermaid block is substituted with the fetched PNG absolute path."""
        mock_fetch.return_value = "/absolute/dummy.png"
        text = "Intro\n```mermaid\ngraph TD;\n    A-->B\n```\nOutro"
        result = preprocess_markdown(text)
        assert "![](/absolute/dummy.png)" in result
        assert "```mermaid" not in result

    @patch("preprocessing.fetch_kroki_mermaid")
    def test_mermaid_renders_fallback(self, mock_fetch) -> None:
        """A failed mermaid API request falls back gracefully without modifying source."""
        mock_fetch.side_effect = Exception("Test Kroki Error")
        text = "Intro\n```mermaid\ngraph TD;\n    A-->B\n```\nOutro"
        result = preprocess_markdown(text)
        assert "```mermaid\ngraph TD;\n    A-->B\n```" in result
        assert "![](" not in result
