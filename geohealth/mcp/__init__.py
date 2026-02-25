"""GeoHealth MCP server — exposes API endpoints as tools for Claude agents.

Requires the ``mcp`` optional dependency: ``pip install geohealth-api[mcp]``
"""

from __future__ import annotations


def __getattr__(name: str):  # noqa: N807
    if name == "mcp":
        from geohealth.mcp.server import mcp

        return mcp
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["mcp"]
