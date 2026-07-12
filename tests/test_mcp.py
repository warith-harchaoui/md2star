"""
Smoke test for the MCP surface (``md2star.mcp``).

Verifies that the MCP wrapper around the FastAPI app imports without error,
re-exposes the underlying FastAPI ``app`` object, and attaches the ``mcp``
handler. Full protocol round-trips belong to a separate integration suite once
the MCP client tooling is stable in CI.

Usage Example
-------------
>>> #   pytest tests/test_mcp.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest

# fastapi_mcp lives in the [mcp] optional extra — skip cleanly if absent.
pytest.importorskip("fastapi_mcp")


def test_mcp_module_imports_and_exposes_app() -> None:
    """The MCP module must import and re-expose the FastAPI app + mcp handler."""
    from md2star import mcp as mcp_module

    assert hasattr(mcp_module, "app"), "md2star.mcp must re-expose `app`."
    assert hasattr(mcp_module, "mcp"), "md2star.mcp must expose the `mcp` handler."


def test_main_entrypoint_is_callable() -> None:
    """The ``md2star-mcp`` console entry point should be a callable."""
    from md2star.mcp import main

    assert callable(main)
