"""MCP-shaped HTTP prototype (opt-in feature).

A clean, minimal MCP-shaped layer over the AFR engine:

- `tools.py`  — tool registry: name, description, JSON-Schema input, handler.
                Handlers call the engine directly (no HTTP round-trip).
- `router.py` — HTTP prototype: GET /mcp/tools, POST /mcp/call. Opt-in feature.
- `server.py` — where a real stdio MCP server would live; currently an
                explicit, runnable stub that prints the tool manifest.

PROTOTYPE STATUS: this module is intentionally NOT a conformant MCP server.
There is no stdio / SSE / JSON-RPC transport, so MCP clients cannot connect to
it yet. It exposes the MCP-shaped tool surface and clean call dispatch over
plain HTTP, so wiring it to the official `mcp` Python SDK is a contained change
inside server.py.
"""

from app.mcp.tools import TOOLS, call_tool, get_tool_definitions  # noqa: F401
