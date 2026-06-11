"""Stdio MCP server — EXPLICIT STUB.

A production version would do, roughly:

    from mcp.server import Server                # official `mcp` package
    from app.mcp.tools import TOOLS

    server = Server("agent-flight-recorder")
    for tool in TOOLS.values():
        server.add_tool(tool.name, tool.description, tool.input_schema,
                        wrap(tool.handler))
    server.run_stdio()

The registry in tools.py is already shaped for that. Until then, running this
module prints the manifest so the surface is inspectable:

    AFR_PREMIUM_ENABLED=true python -m app.mcp.server
"""

from __future__ import annotations

import json

from app.license import is_premium
from app.mcp.tools import get_tool_definitions


def main() -> None:
    if not is_premium():
        print("MCP stub is a premium feature. Set AFR_PREMIUM_ENABLED=true.")
        raise SystemExit(2)
    print("Agent Flight Recorder — MCP server STUB (no stdio transport yet)\n")
    print(json.dumps({"tools": get_tool_definitions()}, indent=2))
    print(
        "\nThis stub exposes the registry only. Wire app/mcp/tools.py to the"
        " official `mcp` SDK in this file to make it a real stdio server."
    )


if __name__ == "__main__":
    main()
