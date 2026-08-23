"""
Weather provenance.

When Open-Meteo is unreachable the ingest generates records so the app
keeps working. That is a reasonable trade. What is not reasonable is
serving those records indistinguishably from measured ones: the rules
engine attaches a real ICAR citation either way, so a farmer reading a
SEVERE warning has no way to tell whether the rainfall behind it was
observed or invented. These tests pin the flag that tells them.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import db  # noqa: E402
from routers.advisories import get_weather  # noqa: E402


def _day(date: str, source: str) -> dict:
    return {
        "date": date,
        "t_max_c": 34.0,
        "t_min_c": 24.0,
        "rain_mm": 12.0,
        "humidity_pct": 80.0,
        "source": source,
    }


@pytest.fixture
def patch_weather(monkeypatch):
    def _apply(records):
        async def fake(grid_id):
            return records

        monkeypatch.setattr(db, "weather_for_grid", fake)

    return _apply


class TestWeatherProvenance:
    @pytest.mark.asyncio
    async def test_real_data_is_not_flagged(self, patch_weather):
        patch_weather([_day(f"2026-08-{d:02d}", "open-meteo") for d in range(1, 8)])
        result = await get_weather("HZB-01")
        assert result["has_synthetic_data"] is False
        assert result["sources"] == ["open-meteo"]

    @pytest.mark.asyncio
    async def test_all_synthetic_is_flagged(self, patch_weather):
        patch_weather([_day(f"2026-08-{d:02d}", "mock-fallback") for d in range(1, 8)])
        result = await get_weather("HZB-01")
        assert result["has_synthetic_data"] is True

    @pytest.mark.asyncio
    async def test_one_synthetic_day_flags_the_window(self, patch_weather):
        """
        Partial contamination still counts. A single generated day can be
        the one that trips a threshold and produces the warning.
        """
        days = [_day(f"2026-08-{d:02d}", "open-meteo") for d in range(1, 7)]
        days.append(_day("2026-08-07", "mock-fallback"))
        patch_weather(days)
        result = await get_weather("HZB-01")
        assert result["has_synthetic_data"] is True
        assert "mock-fallback" in result["sources"]

    @pytest.mark.asyncio
    async def test_empty_window_is_not_flagged(self, patch_weather):
        patch_weather([])
        result = await get_weather("HZB-01")
        assert result["has_synthetic_data"] is False
        assert result["forecast"] == []

    @pytest.mark.asyncio
    async def test_only_the_served_window_is_inspected(self, patch_weather):
        """
        An old synthetic record outside the seven days on screen must not
        raise the flag — the warning has to mean 'what you are looking at'
        or farmers learn to ignore it.
        """
        old = [_day(f"2026-07-{d:02d}", "mock-fallback") for d in range(1, 8)]
        recent = [_day(f"2026-08-{d:02d}", "open-meteo") for d in range(1, 8)]
        patch_weather(old + recent)
        result = await get_weather("HZB-01")
        assert result["has_synthetic_data"] is False
        assert len(result["forecast"]) == 7
