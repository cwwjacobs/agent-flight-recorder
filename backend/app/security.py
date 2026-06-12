"""Optional bearer-token auth.

Unset AFR_API_TOKEN (the default) keeps the current behavior: a fully open
local instance. When AFR_API_TOKEN is set, every endpoint that can write or
read recorded payloads requires `Authorization: Bearer <token>`:

  protected   /runs*  /mcp*  /demo*   (and the same under /api)
  open        /health, /license, API docs, and the static UI shell

/license stays open because clients use it to adapt their UI before they
have credentials; it reveals only the plan, never recorded data. The token
is read per-request, matching the rest of app.config.
"""

from __future__ import annotations

import secrets

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app import config

PROTECTED_PREFIXES = ("/runs", "/mcp", "/demo")


def _is_protected(path: str) -> bool:
    if path.startswith("/api/") or path == "/api":
        path = path[4:] or "/"
    return any(
        path == prefix or path.startswith(prefix + "/") for prefix in PROTECTED_PREFIXES
    )


def _bearer_token(scope: Scope) -> str | None:
    for key, value in scope.get("headers", []):
        if key == b"authorization":
            header = value.decode("latin-1")
            scheme, _, token = header.partition(" ")
            if scheme.lower() == "bearer" and token.strip():
                return token.strip()
            return None
    return None


class TokenAuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        expected = config.api_token()
        if expected is None or not _is_protected(scope["path"]):
            await self.app(scope, receive, send)
            return
        supplied = _bearer_token(scope)
        if supplied is not None and secrets.compare_digest(
            supplied.encode(), expected.encode()
        ):
            await self.app(scope, receive, send)
            return
        response = JSONResponse(
            {"detail": "AFR_API_TOKEN is set on this server — send 'Authorization: Bearer <token>'"},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)
