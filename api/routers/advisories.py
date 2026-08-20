"""
Advisories Router — Section 18.3, 18.4

GET /api/v1/farms/{farm_id}/advisories  — List advisories for a farm
GET /api/v1/advisories/{advisory_id}    — One advisory with evidence
GET /api/v1/weather/{grid_id}           — 7-day forecast for a cell
POST /api/v1/feedback                   — Was this helpful?

CHANGED: the four module-level dicts (_advisories, _events,
_weather_cache, _feedback) are gone. Everything reads and writes through
db.py, so state survives a container restart and is shared across
instances.

Every farm-scoped read is now ownership-checked. Before this change,
knowing any farm id was enough to read that farmer's advisories.
"""

from __future__ import annotations

from datetime import date, datetime

import db
from auth import current_uid, require_owner
from fastapi import APIRouter, Depends, HTTPException, Query
from models import (
    Advisory,
    AdvisoryListResponse,
    ErrorDetail,
    FeedbackCreate,
)

router = APIRouter(prefix="/api/v1", tags=["advisories"])


# ---------------------------------------------------------------------------
# Write helpers used by the ingest pipeline
# ---------------------------------------------------------------------------
async def store_advisory(advisory: dict) -> None:
    await db.save_advisory(advisory)


async def store_event(event: dict) -> None:
    await db.save_event(event)


async def store_weather(key: str, data: dict) -> None:
    await db.save_weather(key, data)


async def get_advisories_for_farm(farm_id: str) -> list[dict]:
    """Return all advisories for a farm, newest first."""
    return await db.advisories_for_farm(farm_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/farms/{farm_id}/advisories", response_model=AdvisoryListResponse)
async def list_advisories(
    farm_id: str,
    limit: int = Query(default=20, le=100),
    language: str = Query(default="hi"),
    since: str | None = Query(default=None),
    uid: str = Depends(current_uid),
):
    """List advisories for a farm, newest first — Section 18.3."""
    farm = await db.get_farm(farm_id)
    require_owner(farm, uid)

    farm_advisories = [
        a
        for a in await db.advisories_for_farm(farm_id)
        if a.get("language", "hi") == language
    ]

    if since:
        try:
            date.fromisoformat(since)  # validate the format, then filter
            farm_advisories = [
                a for a in farm_advisories if a.get("created_at", "")[:10] >= since
            ]
        except ValueError:
            pass

    farm_advisories.sort(key=lambda a: a.get("created_at", ""), reverse=True)
    farm_advisories = farm_advisories[:limit]

    return AdvisoryListResponse(
        farm_id=farm_id,
        count=len(farm_advisories),
        advisories=[Advisory(**a) for a in farm_advisories],
    )


@router.get("/advisories/{advisory_id}")
async def get_advisory(advisory_id: str, uid: str = Depends(current_uid)):
    """
    Get a single advisory with full evidence — Section 18.4.
    Powers the "Kya hua?" screen.
    """
    adv = await db.get_advisory(advisory_id)
    if not adv:
        raise HTTPException(
            status_code=404,
            detail=ErrorDetail(
                code="NOT_FOUND",
                message=f"Advisory {advisory_id} not found.",
            ).model_dump(),
        )

    # The advisory belongs to a farm; the farm belongs to a user.
    farm = await db.get_farm(adv.get("farm_id", ""))
    require_owner(farm, uid)

    # Look up the linked RiskEvent for evidence
    event = await db.get_event(adv.get("event_id", "")) or {}
    evidence = event.get("evidence", {})
    source_note = event.get("source_note", "")

    # Which forecast days the rule actually looked at
    forecast_used = []
    if adv.get("window_start") and adv.get("window_end"):
        grid_id = farm.get("grid_id", "") if farm else ""
        if grid_id:
            ws = adv["window_start"]
            we = adv["window_end"]
            for wd in await db.weather_for_grid(grid_id):
                wd_date = wd.get("date", "")
                if ws <= wd_date <= we:
                    forecast_used.append(
                        {
                            "date": wd_date,
                            "rain_mm": wd.get("rain_mm", 0),
                            "t_max_c": wd.get("t_max_c", 0),
                        }
                    )

    return {
        **adv,
        "evidence": evidence,
        "source_note": source_note,
        "forecast_used": sorted(forecast_used, key=lambda x: x.get("date", "")),
    }


@router.get("/weather/{grid_id}")
async def get_weather(grid_id: str):
    """7-day forecast for a grid cell. Public — weather is not personal data."""
    records = await db.weather_for_grid(grid_id)
    return {
        "grid_id": grid_id,
        "count": len(records),
        "forecast": records[-7:],  # Latest 7 days
    }


@router.post("/feedback", status_code=201)
async def submit_feedback(body: FeedbackCreate, uid: str = Depends(current_uid)):
    """Submit feedback on an advisory — Section 18."""
    farm = await db.get_farm(body.farm_id)
    require_owner(farm, uid)

    feedback = {
        **body.model_dump(),
        "owner_uid": uid,
        "created_at": datetime.now().isoformat(),
    }
    await db.save_feedback(feedback)
    return {"status": "received", "advisory_id": body.advisory_id}


@router.get("/district/summary")
async def district_summary():
    """
    Counts by severity — Section 18, Tier 2.
    Officer dashboard support. Aggregate only: no farm ids, no names,
    nothing that identifies an individual farmer.
    """
    counts = {"SEVERE": 0, "MODERATE": 0, "LOW": 0, "total_farms": 0}
    counts["total_farms"] = await db.count_farms()

    for adv in await db.all_advisories():
        sev = adv.get("severity", "")
        if sev in counts:
            counts[sev] += 1

    return {
        "district": "Hazaribagh",
        "summary": counts,
        "as_of": datetime.now().isoformat(),
    }
