"""
md2star: Model Context Protocol (MCP) surface.

Adapter that exposes the FastAPI app defined in :mod:`md2star.api` as MCP tools,
so an MCP-aware client (Claude Desktop, custom agents, IDE integrations, …) can
call ``health`` / ``doctor`` / ``convert`` as first-class tools. Uses
:mod:`fastapi_mcp` (https://github.com/tadata-org/fastapi_mcp), one line wraps
the whole existing HTTP surface, so the route definitions are never duplicated.

Install the extra to pull in ``fastapi-mcp``::

    pip install 'md2star[api,mcp]'

Then run the MCP server::

    md2star-mcp                     # entry point (see pyproject)
    # or, equivalently:
    python -m md2star.mcp

Usage Example
-------------
>>> # Register the MCP endpoint in your client. It publishes every route
>>> # defined in md2star.api (health / doctor / convert) with the same
>>> # argument names as the FastAPI endpoints.

Author
------
Warith Harchaoui, Ph.D., https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

try:
    from fastapi_mcp import FastApiMCP
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The MCP surface requires the [mcp] extra. Install with: pip install 'md2star[api,mcp]'"
    ) from exc

# Reuse the exact same FastAPI app — MCP is a thin wrapper on top.
from .api import app

# ``FastApiMCP`` mounts an MCP endpoint on the existing FastAPI app; we store the
# wrapped instance at module scope so downstream code (tests, ASGI runners) can
# access both the FastAPI app and the MCP handler.
mcp = FastApiMCP(
    app,
    name="md2star",
    description=(
        "md2star MCP tools: check the environment (doctor) and convert Markdown "
        "to DOCX / PPTX / PDF via Pandoc."
    ),
)
# Attach the MCP endpoint to the FastAPI app. Newer fastapi-mcp releases split
# ``mount()`` into transport-specific ``mount_http()`` (recommended) and
# ``mount_sse()``. Fall back to the legacy ``mount()`` on older versions so a
# range of ``fastapi-mcp`` versions keeps working.
if hasattr(mcp, "mount_http"):
    mcp.mount_http()
else:  # pragma: no cover — legacy fastapi-mcp
    mcp.mount()


def main() -> None:
    """Entry point for the ``md2star-mcp`` console script.

    Boots the FastAPI app (which now serves both the ``/…`` HTTP routes and the
    MCP endpoint) with ``uvicorn`` in single-worker mode. Meant for local /
    container usage; behind a real load balancer, run ``uvicorn`` / ``gunicorn``
    directly against :data:`md2star.api.app`.
    """
    import os

    import uvicorn

    host = os.environ.get("MD2STAR_HOST", "0.0.0.0")
    port = int(os.environ.get("MD2STAR_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, workers=1)


if __name__ == "__main__":  # pragma: no cover
    main()
