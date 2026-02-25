"""Entry point for ``python -m geohealth.mcp``."""

from __future__ import annotations

import argparse

from geohealth.mcp.server import mcp


def main() -> None:
    parser = argparse.ArgumentParser(description="GeoHealth MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP transport (default: 8001)",
    )
    args = parser.parse_args()
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
