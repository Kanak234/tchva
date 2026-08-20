"""
Farms Router — Section 18.2, 18.3

POST /api/v1/farms          — Create a farm
GET  /api/v1/farms/{id}     — Read a farm
PATCH /api/v1/farms/{id}    — Update crop, sowing date, language
GET  /api/v1/me/farms       — Farms belonging to the signed-in user

CHANGED: storage moved from a module-level dict to db.py (Firestore),
and owner_uid now comes from the verified Firebase token instead of the
hardcoded string "demo_user".
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

import db
from auth import current_uid, require_owner
from fastapi import APIRouter, Depends, HTTPException, Request
from models import (
    ErrorDetail,
    Farm,
    FarmCreate,
    FarmResponse,
    FarmUpdate,
)
from rules.crop_calendar import stage_for

router = APIRouter(prefix="/api/v1", tags=["farms"])

# Grid cell mapping — resolve lat/lon to a grid cell
# 4 cells covering Hazaribagh at ~0.25° resolution
GRID_CELLS = [
    {"grid_id": "HZB-01", "lat": 24.00, "lon": 85.25, "name": "Hazaribagh NW"},
    {"grid_id": "HZB-02", "lat": 24.00, "lon": 85.50, "name": "Hazaribagh NE"},
    {"grid_id": "HZB-03", "lat": 23.75, "lon": 85.25, "name": "Hazaribagh SW"},
    {"grid_id": "HZB-04", "lat": 23.75, "lon": 85.50, "name": "Hazaribagh SE"},
]


def resolve_grid(lat: float, lon: float) -> str | None:
    """Resolve a lat/lon to the nearest grid cell within coverage."""
    best_dist = float("inf")
    best_id = None
    for cell in GRID_CELLS:
        dist = abs(lat - cell["lat"]) + abs(lon - cell["lon"])
        if dist < best_dist:
            best_dist = dist
            best_id = cell["grid_id"]
    # Coverage check: must be within ~0.5° of a cell center
    if best_dist > 0.5:
        return None
    return best_id


def _with_stage(farm_data: dict, request: Request) -> dict:
    """Attach the computed growth stage to a stored farm document."""
    today = date.today()
    calendar = getattr(request.app.state, "crop_calendar", None) or {}
    raw_sowing = farm_data["sowing_date"]
    sowing = date.fromisoformat(raw_sowing) if isinstance(raw_sowing, str) else raw_sowing
    stage = stage_for(farm_data["crop"], sowing, today, calendar)
    return {
        **farm_data,
        "growth_stage": stage.name,
        "days_after_sowing": stage.das_current,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post("/farms", status_code=201, response_model=FarmResponse)
async def create_farm(
    body: FarmCreate,
    request: Request,
    uid: str = Depends(current_uid),
):
    """Create a new farm profile — Section 18.2."""
    grid_id = resolve_grid(body.lat, body.lon)
    if grid_id is None:
        raise HTTPException(
            status_code=400,
            detail=ErrorDetail(
                code="OUTSIDE_COVERAGE",
                message="Location does not map to a known grid cell in the demo district.",
                field="lat/lon",
            ).model_dump(),
        )

    farm_id = f"f_{uuid.uuid4().hex[:8]}"
    today = date.today()

    calendar = getattr(request.app.state, "crop_calendar", None) or {}
    stage = stage_for(body.crop, body.sowing_date, today, calendar)

    farm = Farm(
        farm_id=farm_id,
        owner_uid=uid,  # from the verified Firebase ID token
        village=body.village,
        grid_id=grid_id,
        lat=body.lat,
        lon=body.lon,
        crop=body.crop,
        sowing_date=body.sowing_date,
        area_ha=body.area_ha,
        irrigation=body.irrigation,
        language=body.language,
        created_at=datetime.now(),
    )

    await db.save_farm(farm.model_dump(mode="json"))

    return FarmResponse(
        farm_id=farm_id,
        grid_id=grid_id,
        growth_stage=stage.name,
        days_after_sowing=stage.das_current,
        created_at=farm.created_at,
    )


@router.get("/me/farms")
async def my_farms(request: Request, uid: str = Depends(current_uid)):
    """Every farm belonging to the signed-in user."""
    farms = await db.farms_for_owner(uid)
    return {
        "owner_uid": uid,
        "count": len(farms),
        "farms": [_with_stage(f, request) for f in farms],
    }


@router.get("/farms/{farm_id}")
async def get_farm(farm_id: str, request: Request, uid: str = Depends(current_uid)):
    """Read a farm profile — Section 18.2. Owner only."""
    farm_data = await db.get_farm(farm_id)
    require_owner(farm_data, uid)
    return _with_stage(farm_data, request)


@router.patch("/farms/{farm_id}")
async def update_farm(
    farm_id: str,
    body: FarmUpdate,
    request: Request,
    uid: str = Depends(current_uid),
):
    """Update a farm — crop, sowing date, language, irrigation. Owner only."""
    farm_data = await db.get_farm(farm_id)
    require_owner(farm_data, uid)

    patch: dict = {}
    for key, value in body.model_dump(exclude_none=True).items():
        patch[key] = value.isoformat() if isinstance(value, date) else value

    if patch:
        updated = await db.update_farm(farm_id, patch)
        farm_data = updated or {**farm_data, **patch}

    return _with_stage(farm_data, request)


# ---------------------------------------------------------------------------
# Helpers used by the ingest pipeline (no HTTP request in scope)
# ---------------------------------------------------------------------------
async def get_all_farms() -> list[dict]:
    """Return all farms (for the ingest job)."""
    return await db.list_farms()


async def get_farm_by_id(farm_id: str) -> dict | None:
    """Return a single farm document."""
    return await db.get_farm(farm_id)


async def seed_farms(farms: list[dict]) -> int:
    """Write demo farms into storage. Idempotent — same ids overwrite."""
    for f in farms:
        await db.save_farm(f)
    return len(farms)
