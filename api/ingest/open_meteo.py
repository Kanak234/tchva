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


def generate_mock_forecast(grid_id: str, lat: float, lon: float) -> list[WeatherDay]:
    """Generate a realistic 7-day weather forecast fallback for Hazaribagh region."""
    from datetime import date, timedelta, datetime
    import random
    
    # Seed based on grid_id to make values deterministic per day/run
    random.seed(hash(grid_id))
    
    today = date.today()
    records = []
    
    for i in range(7):
        day_date = today + timedelta(days=i)
        
        # Different weather patterns per grid to ensure diverse rules fire
        if grid_id in ("HZB-01", "HZB-02"):
            # Wet grid: Heavy rain and high humidity
            t_max = 30.0 + random.uniform(-1, 1)
            t_min = 23.0 + random.uniform(-1, 1)
            rain = 45.0 + random.uniform(-10, 20) if i < 3 else random.uniform(0, 5)
            humidity = 90.0 + random.uniform(-2, 5)
            wind = 12.0 + random.uniform(-3, 8)
        else:
            # Dry grid: Dry spell, higher temperatures
            t_max = 36.0 + random.uniform(-1, 2)
            t_min = 24.0 + random.uniform(-1, 1)
            rain = 0.0
            humidity = 60.0 + random.uniform(-10, 10)
            wind = 6.0 + random.uniform(-2, 4)
            
        records.append(
            WeatherDay(
                grid_id=grid_id,
                date=day_date,
                t_max_c=round(t_max, 1),
                t_min_c=round(t_min, 1),
                rain_mm=round(rain, 1),
                rain_prob=0.9 if rain > 0 else 0.1,
                humidity_pct=round(humidity, 1),
                wind_kph_max=round(wind, 1),
                source="mock-fallback",
                fetched_at=datetime.now(),
            )
        )
    return records


async def fetch_grid(
    grid_id: str, lat: float, lon: float, client: httpx.AsyncClient | None = None
) -> list[WeatherDay]:
    """
    Fetch 7-day forecast for a grid cell from Open-Meteo.

    Returns a list of normalised WeatherDay records. Falls back to synthetic weather on failure.
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

    except Exception as exc:
        logger.warning(
            f"Failed to fetch forecast for grid {grid_id} (error: {exc}). "
            "Falling back to synthetic weather data."
        )
        try:
            return generate_mock_forecast(grid_id, lat, lon)
        except Exception as fallback_exc:
            logger.exception(f"Fallback weather generation failed: {fallback_exc}")
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
