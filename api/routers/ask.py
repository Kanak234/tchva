"""
Ask Router — Section 18.5 (Bolo Kisan)

POST /api/v1/ask — Voice/text question, grounded answer

CHANGED: farm, forecast and advisory context now come from db.py, and
the caller must own the farm they are asking about. Previously any
farm id could be used to pull that farmer's advisories into a prompt.
"""

from __future__ import annotations

import db
from ai.client import ask_question
from auth import current_uid, require_owner
from fastapi import APIRouter, Depends
from models import AskRequest, AskResponse

router = APIRouter(prefix="/api/v1", tags=["ask"])


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, uid: str = Depends(current_uid)):
    """
    Bolo Kisan — grounded Q&A — Section 18.5.

    Builds context from the farm's profile, forecast, and active advisories,
    then asks Gemini to answer strictly from that context.
    """
    farm = await db.get_farm(body.farm_id)
    require_owner(farm, uid)

    context: dict = {"farm": farm}

    # Add 7-day forecast for the farm's grid cell
    grid_id = farm.get("grid_id", "")
    if grid_id:
        forecast_records = await db.weather_for_grid(grid_id)
        context["forecast"] = forecast_records[-7:]

    # Add the farm's recent advisories
    advisories = await db.advisories_for_farm(body.farm_id)
    context["advisories"] = advisories[:5]

    result = await ask_question(
        question=body.question,
        language=body.language,
        context=context,
    )

    return AskResponse(
        answer_text=result.get("answer_text", ""),
        spoken_script=result.get("spoken_script", ""),
        grounded=result.get("grounded", False),
        used_context=result.get("used_context", []),
        confidence_note=result.get("confidence_note"),
    )
