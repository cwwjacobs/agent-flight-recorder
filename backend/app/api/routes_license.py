"""License/plan introspection (free endpoint — clients use it to adapt UI)."""

from __future__ import annotations

from fastapi import APIRouter

from app.license import license_info

router = APIRouter(tags=["license"])


@router.get("/license")
def get_license() -> dict:
    return license_info()
