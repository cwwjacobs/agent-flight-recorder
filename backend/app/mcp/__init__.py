"""MCP server stub (premium).

A clean, minimal MCP-shaped layer over the AFR engine:

- `tools.py`  — tool registry: name, description, JSON-Schema input, handler.
                Handlers call the engine directly (no HTTP round-trip).
- `router.py` — HTTP stub: GET /mcp/tools, POST /mcp/call. Premium-gated.
- `server.py` — where a real stdio MCP server would live; currently an
                explicit, runnable stub that prints the tool manifest.

STUB STATUS: this module is intentionally not a full MCP implementation — it
exposes the right tool surface and clean call dispatch so wiring it to the
official `mcp` Python SDK is a contained change inside server.py.
"""

from app.mcp.tools import TOOLS, call_tool, get_tool_definitions  # noqa: F401
