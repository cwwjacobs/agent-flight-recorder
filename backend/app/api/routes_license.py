"""Feature-availability introspection (clients use it to adapt the UI)."""

from __future__ import annotations

from fastapi import APIRouter

from app.license import feature_info

router = APIRouter(tags=["features"])


@router.get("/license")
def get_features() -> dict:
    return feature_info()
