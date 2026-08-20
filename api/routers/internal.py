"""
Internal Router — Section 18

POST /internal/ingest — Run the pipeline (scheduler + demo button)
POST /internal/seed   — Load the synthetic demo farms
GET  /internal/status — Which storage backend is live, how many farms

Protected by INTERNAL_TOKEN header. In DEMO_MODE the token check is
relaxed so the on-stage "Run now" button works without a header.

CHANGED: seed farms moved out of this file into data/seed/demo_farms.json
(one place to edit, and the provenance travels with the data), and all
writes go through db.py instead of module-level dicts.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

import db
from fastapi import APIRouter, Header, HTTPException, Request

from routers.advisories import store_advisory, store_event, store_weather
from routers.farms import GRID_CELLS, get_all_farms, seed_farms

logger = logging.getLogger("fasal_kavach.internal")

router = APIRouter(prefix="/internal", tags=["internal"])

# Where the seed file lives depends on how the app was started.
#
#   Local dev:  api/routers/internal.py  ->  <repo>/data/seed/...
#   Docker:     api/ is copied to /app, data/ to /app/data
#               so it is /app/data/seed/..., NOT one level further up.
#
# Getting this wrong fails silently: the seed returns zero farms and the
# demo shows an empty app. Try every layout, and let SEED_PATH be
# whichever one exists.
_HERE = Path(__file__).resolve()
_CANDIDATES = [
    _HERE.parents[2] / "data" / "seed" / "demo_farms.json",  # repo checkout
    _HERE.parents[1] / "data" / "seed" / "demo_farms.json",  # Docker image
    Path("/app/data/seed/demo_farms.json"),                  # explicit fallback
]
SEED_PATH = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])


@lru_cache(maxsize=1)
def load_demo_farms() -> list[dict]:
    """
    Read the synthetic seed farms from disk.

    These are invented farms, clearly marked as such in the file's
    _provenance block. The weather they are evaluated against is not
    invented — it comes from Open-Meteo at ingest time.
    """
    try:
        with open(SEED_PATH, encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        logger.error(json.dumps({"event": "seed_file_missing", "path": str(SEED_PATH)}))
        return []

    farms = payload.get("farms", [])
    # Strip the annotation keys before storing — they document intent for
    # the team, they are not part of the Farm model.
    return [{k: v for k, v in f.items() if not k.startswith("_")} for f in farms]


def _check_token(x_internal_token: str | None) -> None:
    demo = os.getenv("DEMO_MODE", "false").lower() == "true"
    expected = os.getenv("INTERNAL_TOKEN", "")
    if not demo and expected and x_internal_token != expected:
        raise HTTPException(status_code=403, detail="Invalid internal token")


@router.post("/ingest")
async def run_ingest(
    request: Request,
    x_internal_token: str | None = Header(default=None),
):
    """Run the full ingest pipeline — Section 18."""
    _check_token(x_internal_token)

    # Seed demo farms if storage is empty
    current_farms = await get_all_farms()
    if not current_farms:
        seeded = await seed_farms(load_demo_farms())
        current_farms = await get_all_farms()
        logger.info(json.dumps({"event": "seeded", "count": seeded}))

    baselines = getattr(request.app.state, "baselines", {})
    crop_calendar = getattr(request.app.state, "crop_calendar", {})

    from ingest.job import run_pipeline

    result = await run_pipeline(
        farms=current_farms,
        grid_cells=GRID_CELLS,
        baselines=baselines,
        crop_calendar=crop_calendar,
    )

    # Persist results
    for event in result.get("events", []):
        await store_event(event)

    for advisory in result.get("advisories", []):
        await store_advisory(advisory)

    for key, weather in result.get("weather", {}).items():
        await store_weather(key, weather)

    return {
        "status": "ok",
        "backend": db.backend_name(),
        "stats": result.get("stats", {}),
    }


@router.post("/seed")
async def seed_data(x_internal_token: str | None = Header(default=None)):
    """Seed demo farms without running the full pipeline."""
    _check_token(x_internal_token)

    current_farms = await get_all_farms()
    if current_farms:
        return {"status": "already_seeded", "count": len(current_farms)}

    demo_farms = load_demo_farms()
    count = await seed_farms(demo_farms)
    return {"status": "seeded", "count": count, "backend": db.backend_name()}


@router.get("/status")
async def status():
    """
    Which storage backend is actually live.

    Check this before demoing. If it says "memory", Firestore credentials
    did not resolve and your data will vanish on restart.
    """
    return {
        "backend": db.backend_name(),
        "persistent": db.backend_name() == "firestore",
        "farms_stored": await db.count_farms(),
        "demo_mode": os.getenv("DEMO_MODE", "false").lower() == "true",
        "seed_file_found": SEED_PATH.exists(),
    }
