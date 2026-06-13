"""Optional bearer-token auth for the AFR API.

Disabled unless AFR_API_TOKEN is set — so localhost / zero-config use and the
test suite are unaffected. When set, every API route requires either
`Authorization: Bearer <token>` or `X-AFR-Token: <token>`, compared in
constant time. `/health` and the static UI mount stay open.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app import config


def require_auth(
    authorization: str | None = Header(default=None),
    x_afr_token: str | None = Header(default=None),
) -> None:
    expected = config.api_token()
    if not expected:
        return  # auth disabled — no token configured

    presented: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    elif x_afr_token:
        presented = x_afr_token.strip()

    if presented is None or not hmac.compare_digest(presented, expected):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "hint": "send Authorization: Bearer <AFR_API_TOKEN> (or X-AFR-Token)",
            },
            headers={"WWW-Authenticate": "Bearer"},
        )
