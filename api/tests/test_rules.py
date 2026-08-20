"""
Rules Engine Tests — Section 28

Every rule, every branch, boundary values on both sides of each threshold.
"""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import Farm, GrowthStage, WeatherDay
from rules.engine import evaluate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def make_farm(
    crop="paddy",
    sowing_date=date(2026, 7, 15),
    irrigation="rainfed",
    grid_id="HZB-01",
) -> Farm:
    return Farm(
        farm_id="f_test_01",
        owner_uid="test_user",
        village="Barhi",
        grid_id=grid_id,
        lat=24.0,
        lon=85.25,
        crop=crop,
        sowing_date=sowing_date,
        area_ha=1.2,
        irrigation=irrigation,
        language="hi",
    )


def make_forecast(
    rain: list[float] | None = None,
    t_max: list[float] | None = None,
    t_min: list[float] | None = None,
    humidity: list[float] | None = None,
    base_date: date = date(2026, 8, 18),
) -> list[WeatherDay]:
    """Build a 7-day forecast from simple lists."""
    rain = rain or [0.0] * 7
    t_max = t_max or [31.0] * 7
    t_min = t_min or [22.0] * 7
    humidity = humidity or [70.0] * 7

    days = []
    for i in range(min(7, len(rain))):
        days.append(
            WeatherDay(
                grid_id="HZB-01",
                date=base_date + timedelta(days=i),
                t_max_c=t_max[i] if i < len(t_max) else 31.0,
                t_min_c=t_min[i] if i < len(t_min) else 22.0,
                rain_mm=rain[i] if i < len(rain) else 0.0,
                rain_prob=0.5,
                humidity_pct=humidity[i] if i < len(humidity) else 70.0,
                wind_kph_max=10.0,
                source="test",
            )
        )
    return days


def stage_flowering() -> GrowthStage:
    return GrowthStage(
        name="flowering",
        das_start=56,
        das_end=75,
        das_current=65,
        sensitive_water="critical",
        sensitive_heat="critical",
        sensitive_pest="medium",
        input_window=False,
    )


def stage_tillering() -> GrowthStage:
    return GrowthStage(
        name="tillering",
        das_start=36,
        das_end=55,
        das_current=45,
        sensitive_water="high",
        sensitive_heat="low",
        sensitive_pest="high",
        input_window=True,
    )


def stage_maturity() -> GrowthStage:
    return GrowthStage(
        name="maturity",
        das_start=101,
        das_end=120,
        das_current=110,
        sensitive_water="low",
        sensitive_heat="low",
        sensitive_pest="low",
        input_window=False,
    )


BASELINES = {
    "HZB-01": {
        "weeks": {
            "34": {
                "rain_p50": 21.4,
                "rain_p90": 38.2,
                "rain_p95": 74.1,
                "tmax_p50": 31.2,
                "tmax_p90": 35.8,
            }
        }
    }
}

TODAY = date(2026, 8, 18)


# ===========================================================================
# Rule 1: HEAVY_RAIN_PRE_SPRAY
# ===========================================================================
class TestHeavyRainPreSpray:
    def test_fires_at_threshold(self):
        """63 mm in 48h, crop at input window -> fires."""
        farm = make_farm()
        fc = make_forecast(rain=[38.0, 25.0, 0, 0, 0, 0, 0])
        ev = evaluate(farm, fc, stage_tillering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HEAVY_RAIN_PRE_SPRAY"]
        assert len(matches) == 1
        assert matches[0].severity in ("LOW", "MODERATE", "SEVERE")
        assert matches[0].evidence["rain_mm_next_48h"] == 63.0

    def test_does_not_fire_below_threshold(self):
        """21 mm in 48h -> no alert."""
        fc = make_forecast(rain=[12.0, 9.0, 0, 0, 0, 0, 0])
        ev = evaluate(make_farm(), fc, stage_tillering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HEAVY_RAIN_PRE_SPRAY"]
        assert len(matches) == 0

    def test_suppressed_outside_input_window(self):
        """Same rain, but crop at flowering (no input window) -> no alert."""
        fc = make_forecast(rain=[38.0, 25.0, 0, 0, 0, 0, 0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HEAVY_RAIN_PRE_SPRAY"]
        assert len(matches) == 0

    def test_suppressed_at_maturity(self):
        """Same rain, maturity stage -> no spray is due, so no alert."""
        fc = make_forecast(rain=[38.0, 25.0, 0, 0, 0, 0, 0])
        ev = evaluate(make_farm(), fc, stage_maturity(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HEAVY_RAIN_PRE_SPRAY"]
        assert len(matches) == 0


# ===========================================================================
# Rule 2: WATERLOG_RISK
# ===========================================================================
class TestWaterlogRisk:
    def test_fires_above_100mm_3day(self):
        """105 mm over 3 days, rainfed, water-sensitive stage."""
        fc = make_forecast(rain=[40.0, 35.0, 30.0, 0, 0, 0, 0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "WATERLOG_RISK"]
        assert len(matches) == 1
        assert matches[0].evidence["rain_mm_3day"] == 105.0

    def test_below_threshold(self):
        """80 mm over 3 days -> no alert."""
        fc = make_forecast(rain=[30.0, 25.0, 25.0, 0, 0, 0, 0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "WATERLOG_RISK"]
        assert len(matches) == 0

    def test_borewell_irrigation_suppressed(self):
        """High rain but borewell irrigation -> not at waterlog risk."""
        fc = make_forecast(rain=[50.0, 40.0, 40.0, 0, 0, 0, 0])
        farm = make_farm(irrigation="borewell")
        ev = evaluate(farm, fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "WATERLOG_RISK"]
        assert len(matches) == 0


# ===========================================================================
# Rule 3: HEAT_STRESS_FLOWERING
# ===========================================================================
class TestHeatStressFlowering:
    def test_fires_paddy_above_35(self):
        """Two hot days at 37°C during flowering."""
        fc = make_forecast(t_max=[37.0, 38.0, 31.0, 31.0, 31.0, 31.0, 31.0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HEAT_STRESS_FLOWERING"]
        assert len(matches) == 1

    def test_below_threshold_paddy(self):
        """34°C x 2 days -> below 35°C threshold, no alert."""
        fc = make_forecast(t_max=[34.0, 34.0, 30.0, 30.0, 30.0, 30.0, 30.0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HEAT_STRESS_FLOWERING"]
        assert len(matches) == 0

    def test_single_hot_day_not_enough(self):
        """One hot day is not enough (need 2+)."""
        fc = make_forecast(t_max=[37.0, 30.0, 30.0, 30.0, 30.0, 30.0, 30.0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HEAT_STRESS_FLOWERING"]
        assert len(matches) == 0

    def test_low_sensitivity_stage_suppressed(self):
        """Hot days during tillering (low heat sensitivity) -> suppressed."""
        fc = make_forecast(t_max=[37.0, 38.0, 31.0, 31.0, 31.0, 31.0, 31.0])
        ev = evaluate(make_farm(), fc, stage_tillering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HEAT_STRESS_FLOWERING"]
        assert len(matches) == 0


# ===========================================================================
# Rule 4: DRY_SPELL
# ===========================================================================
class TestDrySpell:
    def test_fires_7_dry_days_rainfed(self):
        """7 consecutive dry days on rainfed land."""
        fc = make_forecast(rain=[0.5, 1.0, 0.0, 0.0, 2.0, 0.5, 1.0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "DRY_SPELL"]
        assert len(matches) == 1

    def test_below_threshold_5_days(self):
        """Only 5 dry days -> not enough."""
        fc = make_forecast(rain=[0.5, 1.0, 0.0, 0.0, 2.0, 5.0, 10.0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "DRY_SPELL"]
        assert len(matches) == 0

    def test_irrigated_suppressed(self):
        """Dry spell with canal irrigation -> not an issue."""
        fc = make_forecast(rain=[0.0] * 7)
        farm = make_farm(irrigation="canal")
        ev = evaluate(farm, fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "DRY_SPELL"]
        assert len(matches) == 0


# ===========================================================================
# Rule 5: PEST_WEATHER_WINDOW
# ===========================================================================
class TestPestWeather:
    def test_fires_high_humidity_warm_nights(self):
        """3+ days of high humidity and warm nights."""
        fc = make_forecast(
            humidity=[90.0, 88.0, 92.0, 86.0, 70.0, 65.0, 60.0],
            t_min=[24.0, 25.0, 23.0, 24.0, 22.0, 20.0, 18.0],
        )
        ev = evaluate(make_farm(), fc, stage_tillering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "PEST_WEATHER_WINDOW"]
        assert len(matches) == 1

    def test_low_humidity_no_fire(self):
        """Humidity below 85% -> no pest alert."""
        fc = make_forecast(
            humidity=[75.0, 78.0, 80.0, 72.0, 70.0, 65.0, 60.0],
            t_min=[24.0, 25.0, 23.0, 24.0, 22.0, 20.0, 18.0],
        )
        ev = evaluate(make_farm(), fc, stage_tillering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "PEST_WEATHER_WINDOW"]
        assert len(matches) == 0


# ===========================================================================
# Rule 6: HARVEST_RAIN_CLASH
# ===========================================================================
class TestHarvestRainClash:
    def test_fires_near_maturity(self):
        """Rain during maturity stage."""
        fc = make_forecast(rain=[30.0, 15.0, 0, 0, 0, 0, 0])
        ev = evaluate(make_farm(), fc, stage_maturity(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HARVEST_RAIN_CLASH"]
        assert len(matches) == 1

    def test_not_near_harvest(self):
        """Rain during flowering -> not relevant for harvest."""
        fc = make_forecast(rain=[30.0, 15.0, 0, 0, 0, 0, 0])
        ev = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "HARVEST_RAIN_CLASH"]
        assert len(matches) == 0


# ===========================================================================
# Rule 7: FROST_RISK
# ===========================================================================
class TestFrostRisk:
    def test_fires_wheat_below_4(self):
        """Frost for wheat."""
        fc = make_forecast(t_min=[3.0, 2.0, 5.0, 6.0, 7.0, 8.0, 9.0])
        farm = make_farm(crop="wheat")
        stage = GrowthStage(
            name="tillering",
            das_start=21,
            das_end=45,
            das_current=30,
            sensitive_water="high",
            sensitive_heat="low",
            sensitive_pest="medium",
            input_window=True,
        )
        ev = evaluate(farm, fc, stage, BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "FROST_RISK"]
        assert len(matches) == 1

    def test_no_frost_for_paddy(self):
        """Frost rule only applies to wheat and tomato."""
        fc = make_forecast(t_min=[3.0, 2.0, 5.0, 6.0, 7.0, 8.0, 9.0])
        farm = make_farm(crop="paddy")
        ev = evaluate(farm, fc, stage_flowering(), BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "FROST_RISK"]
        assert len(matches) == 0

    def test_above_threshold(self):
        """t_min = 5°C, above 4°C threshold -> no alert."""
        fc = make_forecast(t_min=[5.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        farm = make_farm(crop="wheat")
        stage = GrowthStage(
            name="tillering",
            das_start=21,
            das_end=45,
            das_current=30,
            sensitive_water="high",
            sensitive_heat="low",
            sensitive_pest="medium",
            input_window=True,
        )
        ev = evaluate(farm, fc, stage, BASELINES, TODAY)
        matches = [e for e in ev if e.rule_id == "FROST_RISK"]
        assert len(matches) == 0


# ===========================================================================
# General engine tests
# ===========================================================================
class TestEngineGeneral:
    def test_empty_forecast_returns_no_events(self):
        ev = evaluate(make_farm(), [], stage_flowering(), BASELINES, TODAY)
        assert ev == []

    def test_event_id_is_deterministic(self):
        """Same inputs produce the same event_id."""
        fc = make_forecast(rain=[40.0, 35.0, 30.0, 0, 0, 0, 0])
        ev1 = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        ev2 = evaluate(make_farm(), fc, stage_flowering(), BASELINES, TODAY)
        ids1 = {e.event_id for e in ev1}
        ids2 = {e.event_id for e in ev2}
        assert ids1 == ids2

    def test_evidence_is_populated(self):
        """Every event has a non-empty evidence dict."""
        fc = make_forecast(rain=[50.0, 40.0, 30.0, 0, 0, 0, 0])
        ev = evaluate(make_farm(), fc, stage_tillering(), BASELINES, TODAY)
        for e in ev:
            assert e.evidence, f"Event {e.rule_id} has empty evidence"
            assert "days_since_sowing" in e.evidence
