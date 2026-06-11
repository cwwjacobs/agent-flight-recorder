"""HTTP face of the MCP stub (premium-gated)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.errors import not_found_to_404
from app.license import premium_feature
from app.mcp.tools import call_tool, get_tool_definitions

router = APIRouter(prefix="/mcp", tags=["mcp"], dependencies=[premium_feature("mcp")])


class MCPCallIn(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


@router.get("/tools")
def list_tools() -> dict:
    return {"tools": get_tool_definitions(), "stub": True}


@router.post("/call")
def call(body: MCPCallIn) -> dict:
    try:
        with not_found_to_404():
            result = call_tool(body.tool, body.arguments)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown MCP tool: {body.tool}")
    except TypeError as exc:
        raise HTTPException(status_code=422, detail=f"bad arguments for {body.tool}: {exc}")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"ok": True, "tool": body.tool, "result": result}
