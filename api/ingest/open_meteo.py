"""
Open-Meteo Client — Section 13.2

Fetches 7-day forecast for a grid cell and normalises into WeatherDay records.
normalise() is the ONLY function that knows provider field names.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime

import httpx
from models import WeatherDay

logger = logging.getLogger("fasal_kavach.ingest")

BASE = os.getenv("OPEN_METEO_BASE", "https://api.open-meteo.com/v1")

PARAMS = {
    "daily": ",".join(
        [
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_sum",
            "precipitation_probability_max",
            "relative_humidity_2m_mean",
            "wind_speed_10m_max",
        ]
    ),
    "timezone": "Asia/Kolkata",
    "forecast_days": "7",
}


async def fetch_grid(
    grid_id: str, lat: float, lon: float, client: httpx.AsyncClient | None = None
) -> list[WeatherDay]:
    """
    Fetch 7-day forecast for a grid cell from Open-Meteo.

    Returns a list of normalised WeatherDay records.
    """
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)

    try:
        r = await client.get(
            f"{BASE}/forecast",
            params={
                **PARAMS,
                "latitude": str(lat),
                "longitude": str(lon),
            },
        )
        r.raise_for_status()
        data = r.json()
        return normalise(grid_id, data)

    except httpx.HTTPError:
        logger.exception(f"Failed to fetch forecast for grid {grid_id}")
        return []
    except Exception:
        logger.exception(f"Unexpected error fetching grid {grid_id}")
        return []


def normalise(grid_id: str, raw: dict) -> list[WeatherDay]:
    """
    Normalise Open-Meteo response into canonical WeatherDay records.

    This is the ONLY function that knows provider field names. When Open-Meteo
    changes a field name, exactly this function changes.

    Validation gates (Section 13.3):
    - Range checks on temperature, rainfall, humidity
    - t_min <= t_max ordering check
    """
    daily = raw.get("daily", {})
    dates = daily.get("time", [])
    t_maxes = daily.get("temperature_2m_max", [])
    t_mins = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])
    precip_prob = daily.get("precipitation_probability_max", [])
    humidity = daily.get("relative_humidity_2m_mean", [])
    wind = daily.get("wind_speed_10m_max", [])

    now = datetime.now()
    records: list[WeatherDay] = []
    dropped = 0

    for i, d_str in enumerate(dates):
        try:
            d = date.fromisoformat(d_str)

            t_max = float(t_maxes[i]) if i < len(t_maxes) and t_maxes[i] is not None else None
            t_min = float(t_mins[i]) if i < len(t_mins) and t_mins[i] is not None else None
            rain = float(precip[i]) if i < len(precip) and precip[i] is not None else 0.0
            rain_p = float(precip_prob[i]) / 100.0 if i < len(precip_prob) and precip_prob[i] is not None else 0.0
            hum = float(humidity[i]) if i < len(humidity) and humidity[i] is not None else 50.0
            wnd = float(wind[i]) if i < len(wind) and wind[i] is not None else 0.0

            # Validation gate: temperature range -10 to 55
            if t_max is None or t_min is None:
                dropped += 1
                continue
            if not (-10 <= t_max <= 55) or not (-10 <= t_min <= 55):
                logger.warning(f"Grid {grid_id} day {d}: temp out of range ({t_min}, {t_max})")
                dropped += 1
                continue

            # Validation gate: t_min <= t_max
            if t_min > t_max:
                logger.warning(f"Grid {grid_id} day {d}: t_min > t_max ({t_min} > {t_max})")
                dropped += 1
                continue

            # Validation gate: rainfall 0 to 500
            if not (0 <= rain <= 500):
                logger.warning(f"Grid {grid_id} day {d}: rain out of range ({rain})")
                dropped += 1
                continue

            # Humidity: clamp to 0-100 rather than drop
            hum = max(0.0, min(100.0, hum))

            records.append(
                WeatherDay(
                    grid_id=grid_id,
                    date=d,
                    t_max_c=t_max,
                    t_min_c=t_min,
                    rain_mm=rain,
                    rain_prob=min(1.0, max(0.0, rain_p)),
                    humidity_pct=hum,
                    wind_kph_max=wnd,
                    source="open-meteo",
                    fetched_at=now,
                )
            )

        except (ValueError, IndexError, TypeError) as e:
            logger.warning(f"Grid {grid_id} day {i}: parse error: {e}")
            dropped += 1

    if dropped:
        logger.info(f"Grid {grid_id}: dropped {dropped} days, kept {len(records)}")

    # Completeness check: at least 5 of 7 days
    if len(records) < 5:
        logger.warning(
            f"Grid {grid_id}: only {len(records)} valid days, need at least 5. "
            "Keeping previous cache entry."
        )
        return []

    return records
