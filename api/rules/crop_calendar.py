"""
Crop Calendar Module — Section 17

Converts a sowing date into a growth stage, which is what makes an advisory
specific rather than generic.

Data comes from data/crop_calendar.csv (built by M3 from KVK/ICAR material).
"""

from __future__ import annotations

import csv
import os
from datetime import date

from models import GrowthStage

# ---------------------------------------------------------------------------
# Calendar data — loaded once at startup
# ---------------------------------------------------------------------------
CropCalendarData = dict[str, list[dict]]

_CALENDAR_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "crop_calendar.csv"
)


def load_crop_calendar(path: str | None = None) -> CropCalendarData:
    """Load crop_calendar.csv into a dict keyed by crop name."""
    path = path or _CALENDAR_PATH
    calendar: CropCalendarData = {}

    try:
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                crop = row["crop"].strip().lower()
                if crop not in calendar:
                    calendar[crop] = []
                calendar[crop].append(
                    {
                        "name": row["stage"].strip(),
                        "das_start": int(row["das_start"]),
                        "das_end": int(row["das_end"]),
                        "sensitive_water": row.get("sensitive_water", "low").strip(),
                        "sensitive_heat": row.get("sensitive_heat", "low").strip(),
                        "sensitive_pest": row.get("sensitive_pest", "low").strip(),
                        "input_window": row.get("input_window", "false").strip().lower()
                        == "true",
                    }
                )
    except FileNotFoundError:
        # Fallback: hardcoded calendar for the 4 demo crops
        calendar = _default_calendar()

    return calendar


def stage_for(
    crop: str,
    sowing: date,
    today: date,
    calendar: CropCalendarData | None = None,
) -> GrowthStage:
    """
    Pure function: given crop, sowing date and today, return the GrowthStage.

    Edge cases (Section 17.3):
    - Sowing in future → PRE_SOWING
    - DAS beyond last stage → POST_HARVEST
    - Crop not in calendar → POST_HARVEST (reject at API level)
    """
    das = (today - sowing).days

    if das < 0:
        return GrowthStage(
            name="pre_sowing",
            das_start=-999,
            das_end=-1,
            das_current=das,
        )

    cal = calendar or _default_calendar()
    stages = cal.get(crop.lower(), [])

    for row in stages:
        if row["das_start"] <= das <= row["das_end"]:
            return GrowthStage(
                name=row["name"],
                das_start=row["das_start"],
                das_end=row["das_end"],
                das_current=das,
                sensitive_water=row.get("sensitive_water", "low"),
                sensitive_heat=row.get("sensitive_heat", "low"),
                sensitive_pest=row.get("sensitive_pest", "low"),
                input_window=row.get("input_window", False),
            )

    return GrowthStage(
        name="post_harvest",
        das_start=9000,
        das_end=9999,
        das_current=das,
    )


def _default_calendar() -> CropCalendarData:
    """
    Hardcoded crop calendar for 4 demo crops.
    Source: ICAR-NRRI & KVK Hazaribagh recommended practices.
    DAS = Days After Sowing.
    """
    return {
        "paddy": [
            {"name": "nursery", "das_start": 0, "das_end": 21, "sensitive_water": "high", "sensitive_heat": "medium", "sensitive_pest": "high", "input_window": True},
            {"name": "transplant_establish", "das_start": 22, "das_end": 35, "sensitive_water": "critical", "sensitive_heat": "medium", "sensitive_pest": "medium", "input_window": True},
            {"name": "tillering", "das_start": 36, "das_end": 55, "sensitive_water": "high", "sensitive_heat": "low", "sensitive_pest": "high", "input_window": True},
            {"name": "flowering", "das_start": 56, "das_end": 75, "sensitive_water": "critical", "sensitive_heat": "critical", "sensitive_pest": "medium", "input_window": False},
            {"name": "grain_fill", "das_start": 76, "das_end": 100, "sensitive_water": "high", "sensitive_heat": "critical", "sensitive_pest": "low", "input_window": False},
            {"name": "maturity", "das_start": 101, "das_end": 120, "sensitive_water": "low", "sensitive_heat": "low", "sensitive_pest": "low", "input_window": False},
        ],
        "maize": [
            {"name": "vegetative", "das_start": 0, "das_end": 35, "sensitive_water": "medium", "sensitive_heat": "medium", "sensitive_pest": "high", "input_window": True},
            {"name": "tasseling", "das_start": 36, "das_end": 60, "sensitive_water": "critical", "sensitive_heat": "critical", "sensitive_pest": "medium", "input_window": True},
            {"name": "grain_fill", "das_start": 61, "das_end": 95, "sensitive_water": "high", "sensitive_heat": "high", "sensitive_pest": "low", "input_window": False},
            {"name": "maturity", "das_start": 96, "das_end": 120, "sensitive_water": "low", "sensitive_heat": "low", "sensitive_pest": "low", "input_window": False},
        ],
        "wheat": [
            {"name": "germination", "das_start": 0, "das_end": 20, "sensitive_water": "high", "sensitive_heat": "low", "sensitive_pest": "low", "input_window": True},
            {"name": "tillering", "das_start": 21, "das_end": 45, "sensitive_water": "high", "sensitive_heat": "low", "sensitive_pest": "medium", "input_window": True},
            {"name": "jointing", "das_start": 46, "das_end": 65, "sensitive_water": "high", "sensitive_heat": "medium", "sensitive_pest": "medium", "input_window": True},
            {"name": "flowering", "das_start": 66, "das_end": 85, "sensitive_water": "critical", "sensitive_heat": "critical", "sensitive_pest": "medium", "input_window": False},
            {"name": "grain_fill", "das_start": 86, "das_end": 110, "sensitive_water": "high", "sensitive_heat": "high", "sensitive_pest": "low", "input_window": False},
            {"name": "maturity", "das_start": 111, "das_end": 135, "sensitive_water": "low", "sensitive_heat": "low", "sensitive_pest": "low", "input_window": False},
        ],
        "tomato": [
            {"name": "seedling", "das_start": 0, "das_end": 25, "sensitive_water": "high", "sensitive_heat": "medium", "sensitive_pest": "high", "input_window": True},
            {"name": "vegetative", "das_start": 26, "das_end": 45, "sensitive_water": "medium", "sensitive_heat": "medium", "sensitive_pest": "high", "input_window": True},
            {"name": "flowering", "das_start": 46, "das_end": 65, "sensitive_water": "critical", "sensitive_heat": "critical", "sensitive_pest": "high", "input_window": False},
            {"name": "fruiting", "das_start": 66, "das_end": 90, "sensitive_water": "high", "sensitive_heat": "high", "sensitive_pest": "medium", "input_window": False},
            {"name": "harvest", "das_start": 91, "das_end": 120, "sensitive_water": "low", "sensitive_heat": "medium", "sensitive_pest": "low", "input_window": False},
        ],
    }
