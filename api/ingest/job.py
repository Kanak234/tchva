"""
Ingest Job — Section 13.1

The scheduled pipeline that ties everything together:
1. Fetch forecast for each active grid cell
2. Run rules engine for every active farm
3. Generate or cache advisories for each new RiskEvent
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date

from ai import cache as ai_cache
from ai.client import generate_advisory
from models import Advisory, Farm, RiskEvent, WeatherDay
from rules.crop_calendar import stage_for
from rules.engine import evaluate
from rules.templates import get_template

logger = logging.getLogger("fasal_kavach.ingest")


async def run_pipeline(
    farms: list[dict],
    grid_cells: list[dict],
    baselines: dict,
    crop_calendar: dict,
    weather_store: dict | None = None,
) -> dict:
    """
    Run the full ingest + evaluate + generate pipeline.

    Returns a summary dict for structured logging (Section 20.3).
    """
    import httpx

    from ingest.open_meteo import fetch_grid

    run_id = str(uuid.uuid4())[:8]
    start = time.monotonic()
    today = date.today()

    stats = {
        "event": "ingest_complete",
        "run_id": run_id,
        "grids_fetched": 0,
        "days_dropped": 0,
        "farms_evaluated": 0,
        "events_created": 0,
        "advisories_generated": 0,
        "cache_hits": 0,
        "ai_failures": 0,
        "template_fallbacks": 0,
        "duration_ms": 0,
    }

    # -----------------------------------------------------------------------
    # Step 1: Fetch forecasts
    # -----------------------------------------------------------------------
    weather_by_grid: dict[str, list[WeatherDay]] = {}
    if weather_store is None:
        weather_store = {}

    async with httpx.AsyncClient(timeout=30.0) as client:
        for cell in grid_cells:
            grid_id = cell["grid_id"]
            lat = cell["lat"]
            lon = cell["lon"]

            forecast = await fetch_grid(grid_id, lat, lon, client)
            if forecast:
                weather_by_grid[grid_id] = forecast
                # Store in weather cache
                for wd in forecast:
                    key = f"{wd.grid_id}_{wd.date.isoformat()}"
                    weather_store[key] = wd.model_dump(mode="json")
                stats["grids_fetched"] += 1
            else:
                logger.warning(f"No forecast for grid {grid_id}")

    # -----------------------------------------------------------------------
    # Step 2 & 3: Evaluate rules and generate advisories for each farm
    # -----------------------------------------------------------------------
    all_events: list[RiskEvent] = []
    all_advisories: list[Advisory] = []
    seen_event_ids: set[str] = set()

    for farm_dict in farms:
        try:
            farm = Farm(**farm_dict) if isinstance(farm_dict, dict) else farm_dict
            forecast = weather_by_grid.get(farm.grid_id, [])

            if not forecast:
                continue

            # Get growth stage
            stage = stage_for(
                farm.crop, farm.sowing_date, today, crop_calendar
            )

            # Evaluate rules
            events = evaluate(farm, forecast, stage, baselines, today)
            stats["farms_evaluated"] += 1

            for event in events:
                # Idempotency: skip if we already generated for this event
                if event.event_id in seen_event_ids:
                    continue
                seen_event_ids.add(event.event_id)

                all_events.append(event)
                stats["events_created"] += 1

                # Generate advisory for each supported language
                for lang in [farm.language, "en"] if farm.language != "en" else ["en"]:
                    advisory = await _generate_or_cache_advisory(
                        event, lang, farm, stats
                    )
                    if advisory:
                        all_advisories.append(advisory)

        except Exception:
            logger.exception(f"Error evaluating farm {farm_dict.get('farm_id', '?')}")
            # Per-farm try/except — one bad record must not kill the batch

    stats["duration_ms"] = int((time.monotonic() - start) * 1000)
    logger.info(json.dumps(stats))

    return {
        "stats": stats,
        "events": [e.model_dump(mode="json") for e in all_events],
        "advisories": [a.model_dump(mode="json") for a in all_advisories],
        "weather": weather_store,
    }


async def _generate_or_cache_advisory(
    event: RiskEvent,
    language: str,
    farm: Farm,
    stats: dict,
) -> Advisory | None:
    """Generate an advisory, checking cache first, falling back to templates."""
    advisory_id = f"{event.event_id}_{language}"

    # Check cache
    ck = ai_cache.cache_key(
        event.rule_id,
        event.crop,
        event.growth_stage,
        event.severity,
        language,
        event.evidence,
    )
    cached = ai_cache.get(ck)
    if cached:
        stats["cache_hits"] += 1
        return Advisory(
            advisory_id=advisory_id,
            event_id=event.event_id,
            farm_id=event.farm_id,
            language=language,
            severity=event.severity,
            rule_id=event.rule_id,
            headline=cached["headline"],
            body=cached["body"],
            actions=cached["actions"],
            spoken_script=cached["spoken_script"],
            generated_by="gemini",
            model_version="gemini-2.5-flash",
            window_start=event.window_start,
            window_end=event.window_end,
        )

    # Try Gemini
    event_dict = event.model_dump(mode="json")
    event_dict["area_ha"] = farm.area_ha
    event_dict["irrigation"] = farm.irrigation
    event_dict["village"] = farm.village

    result = await generate_advisory(event_dict, language)

    if result:
        ai_cache.put(ck, result)
        stats["advisories_generated"] += 1
        return Advisory(
            advisory_id=advisory_id,
            event_id=event.event_id,
            farm_id=event.farm_id,
            language=language,
            severity=event.severity,
            rule_id=event.rule_id,
            headline=result["headline"],
            body=result["body"],
            actions=result["actions"],
            spoken_script=result["spoken_script"],
            generated_by="gemini",
            model_version="gemini-2.5-flash",
            window_start=event.window_start,
            window_end=event.window_end,
        )

    # Fallback to template
    stats["ai_failures"] += 1
    template = get_template(
        event.rule_id,
        language,
        event.evidence,
        crop=event.crop,
        stage_window=event.growth_stage,
    )
    if template:
        stats["template_fallbacks"] += 1
        return Advisory(
            advisory_id=advisory_id,
            event_id=event.event_id,
            farm_id=event.farm_id,
            language=language,
            severity=event.severity,
            rule_id=event.rule_id,
            headline=template["headline"],
            body=template["body"],
            actions=template["actions"],
            spoken_script=template["spoken_script"],
            generated_by="template",
            window_start=event.window_start,
            window_end=event.window_end,
        )

    return None
