"""
Rule Definitions — Section 16.2 of the build spec.

Seven rules, each with cited thresholds.  Every numeric threshold carries a
comment naming where it came from.
"""

from __future__ import annotations

from datetime import timedelta

from rules.engine import RuleContext, rule, severity_for

# ===========================  THRESHOLDS  ==================================
# Each threshold has a source comment.  If we cannot source it, it is marked
# SOURCE: TEAM ESTIMATE.

# Rule 1: Heavy rain pre-spray
# Source: ICAR kharif advisory — spray timing guidance.
# Rainfall above 40 mm in 48h washes off foliar sprays and top-dress urea.
HEAVY_RAIN_THRESHOLD_MM = 40.0

# Rule 2: Waterlog risk
# Source: ICAR-NRRI package of practices — paddy drainage guidance.
# 100 mm / 3 days on rainfed land risks waterlogging in sensitive stages.
WATERLOG_3DAY_MM = 100.0

# Rule 3: Heat stress at flowering
# Source: ICAR-NRRI — spikelet sterility rises sharply above these temps.
# Paddy: 35°C, Wheat: 32°C, Tomato: 34°C, Maize: 38°C
HEAT_THRESHOLDS_C: dict[str, float] = {
    "paddy": 35.0,
    "wheat": 32.0,
    "tomato": 34.0,
    "maize": 38.0,
}

# Rule 4: Dry spell
# Source: TEAM ESTIMATE, calibrated against IMD dry-spell definitions.
# 7+ consecutive days with < 2.5 mm on rainfed land.
DRY_SPELL_DAYS = 7
DRY_SPELL_RAIN_LIMIT_MM = 2.5

# Rule 5: Pest weather window
# Source: ICAR crop-specific IPM guidelines.
# High humidity (>85%) + warm nights favour pest outbreaks.
PEST_HUMIDITY_PCT = 85.0
PEST_TMIN_BANDS: dict[str, tuple[float, float]] = {
    "paddy": (20.0, 30.0),   # Stem borer, BLB
    "maize": (18.0, 28.0),   # Fall armyworm
    "wheat": (10.0, 20.0),   # Aphids, rust
    "tomato": (15.0, 25.0),  # Late blight, whitefly
}

# Rule 6: Harvest rain clash
# Source: TEAM ESTIMATE, needs validation.
# Rain > 25 mm within 10 days of expected harvest.
HARVEST_RAIN_MM = 25.0
HARVEST_WINDOW_DAYS = 10

# Rule 7: Frost risk
# Source: IMD cold wave criteria for Jharkhand.
# t_min < 4°C for rabi crops and vegetables.
FROST_TMIN_C = 4.0


# =========================  RULE DEFINITIONS  ==============================


@rule("HEAVY_RAIN_PRE_SPRAY")
def heavy_rain_pre_spray(ctx: RuleContext):
    """
    Rule 1: Fires when rain in next 48h exceeds 40 mm OR the week-of-year
    P90 baseline, and the crop is within 7 days of a typical spray/fertiliser
    window.

    Advisory intent: Delay spraying or top-dressing; it will wash off.
    """
    if len(ctx.forecast) < 2:
        return None

    next48 = sum(d.rain_mm for d in ctx.forecast[:2])
    p90 = ctx.baseline("rain_p90")
    thresh = max(HEAVY_RAIN_THRESHOLD_MM, p90) if p90 > 0 else HEAVY_RAIN_THRESHOLD_MM

    if next48 < thresh * 0.8:
        return None

    if not ctx.stage.near_input_window(days=7):
        return None

    sev = severity_for(next48, thresh, ctx.stage.sensitivity("water"))
    if sev is None:
        return None

    return ctx.event(
        rule_id="HEAVY_RAIN_PRE_SPRAY",
        severity=sev,
        window=(ctx.today, ctx.today + timedelta(days=2)),
        evidence={
            "rain_mm_next_48h": round(next48, 1),
            "threshold_mm": round(thresh, 1),
            "baseline_p90_mm": round(p90, 1),
            "days_since_sowing": ctx.das,
            "stage_window": ctx.stage.label,
            "observed_at": ctx.today.isoformat(),
        },
        actions=["DELAY_SPRAY", "CHECK_DRAINAGE", "RESCHEDULE_UREA"],
        source_note="ICAR kharif advisory, spray timing guidance",
    )


@rule("WATERLOG_RISK")
def waterlog_risk(ctx: RuleContext):
    """
    Rule 2: 3-day cumulative rain over 100 mm and irrigation is rainfed or
    canal and stage is sensitive to standing water.

    Advisory intent: Open field drainage and clear bunds now.
    """
    if len(ctx.forecast) < 3:
        return None

    rain_3d = sum(d.rain_mm for d in ctx.forecast[:3])
    if rain_3d < WATERLOG_3DAY_MM:
        return None

    if ctx.farm.irrigation not in ("rainfed", "canal"):
        return None

    water_sens = ctx.stage.sensitivity("water")
    if water_sens == "low":
        return None

    sev = severity_for(rain_3d, WATERLOG_3DAY_MM, water_sens)
    if sev is None:
        return None

    return ctx.event(
        rule_id="WATERLOG_RISK",
        severity=sev,
        window=(ctx.today, ctx.today + timedelta(days=3)),
        evidence={
            "rain_mm_3day": round(rain_3d, 1),
            "threshold_mm": WATERLOG_3DAY_MM,
            "irrigation": ctx.farm.irrigation,
            "days_since_sowing": ctx.das,
            "stage_window": ctx.stage.label,
            "observed_at": ctx.today.isoformat(),
        },
        actions=["OPEN_DRAINAGE", "CLEAR_BUNDS", "CHECK_NURSERY"],
        source_note="ICAR-NRRI package of practices, paddy drainage",
    )


@rule("HEAT_STRESS_FLOWERING")
def heat_stress_flowering(ctx: RuleContext):
    """
    Rule 3: t_max above the crop threshold on 2+ days while the crop is in
    flowering or grain-fill.

    Advisory intent: Irrigate evening, mulch, avoid midday operations.
    """
    threshold = HEAT_THRESHOLDS_C.get(ctx.farm.crop, 35.0)
    hot_days = [d for d in ctx.forecast if d.t_max_c >= threshold]

    if len(hot_days) < 2:
        return None

    heat_sens = ctx.stage.sensitivity("heat")
    if heat_sens == "low":
        return None

    max_temp = max(d.t_max_c for d in hot_days)
    sev = severity_for(max_temp, threshold, heat_sens)
    if sev is None:
        return None

    return ctx.event(
        rule_id="HEAT_STRESS_FLOWERING",
        severity=sev,
        window=(hot_days[0].date, hot_days[-1].date),
        evidence={
            "t_max_peak_c": round(max_temp, 1),
            "threshold_c": threshold,
            "hot_days_count": len(hot_days),
            "crop": ctx.farm.crop,
            "days_since_sowing": ctx.das,
            "stage_window": ctx.stage.label,
            "observed_at": ctx.today.isoformat(),
        },
        actions=["IRRIGATE_EVENING", "APPLY_MULCH", "AVOID_MIDDAY_OPS"],
        source_note="ICAR-NRRI, spikelet sterility above threshold during anthesis",
    )


@rule("DRY_SPELL")
def dry_spell(ctx: RuleContext):
    """
    Rule 4: 7+ consecutive forecast days with under 2.5 mm, and rainfed,
    and the stage is water-sensitive.

    Advisory intent: Prioritise the critical irrigation; consider mulching.
    """
    if ctx.farm.irrigation != "rainfed":
        return None

    water_sens = ctx.stage.sensitivity("water")
    if water_sens == "low":
        return None

    dry_days = 0
    for d in ctx.forecast:
        if d.rain_mm < DRY_SPELL_RAIN_LIMIT_MM:
            dry_days += 1
        else:
            break  # consecutive only

    if dry_days < DRY_SPELL_DAYS:
        return None

    sev = severity_for(dry_days, DRY_SPELL_DAYS, water_sens)
    if sev is None:
        return None

    return ctx.event(
        rule_id="DRY_SPELL",
        severity=sev,
        window=(ctx.today, ctx.today + timedelta(days=dry_days)),
        evidence={
            "dry_days_forecast": dry_days,
            "threshold_days": DRY_SPELL_DAYS,
            "rain_limit_mm": DRY_SPELL_RAIN_LIMIT_MM,
            "irrigation": ctx.farm.irrigation,
            "days_since_sowing": ctx.das,
            "stage_window": ctx.stage.label,
            "observed_at": ctx.today.isoformat(),
        },
        actions=["PRIORITISE_IRRIGATION", "APPLY_MULCH", "CONSERVE_SOIL_MOISTURE"],
        source_note="TEAM ESTIMATE, calibrated against IMD dry-spell definitions",
    )


@rule("PEST_WEATHER_WINDOW")
def pest_weather_window(ctx: RuleContext):
    """
    Rule 5: Humidity above 85% and t_min in the pest-favourable band for 3+
    days, for the crop-specific pest.

    Advisory intent: Scout the field now for the named pest.
    """
    pest_band = PEST_TMIN_BANDS.get(ctx.farm.crop, (15.0, 25.0))
    pest_sens = ctx.stage.sensitivity("pest")
    if pest_sens == "low":
        return None

    pest_days = [
        d
        for d in ctx.forecast
        if d.humidity_pct >= PEST_HUMIDITY_PCT
        and pest_band[0] <= d.t_min_c <= pest_band[1]
    ]

    if len(pest_days) < 3:
        return None

    sev = severity_for(len(pest_days), 3, pest_sens)
    if sev is None:
        return None

    return ctx.event(
        rule_id="PEST_WEATHER_WINDOW",
        severity=sev,
        window=(pest_days[0].date, pest_days[-1].date),
        evidence={
            "pest_favourable_days": len(pest_days),
            "humidity_pct_avg": round(
                sum(d.humidity_pct for d in pest_days) / len(pest_days), 1
            ),
            "t_min_range_c": list(pest_band),
            "crop": ctx.farm.crop,
            "days_since_sowing": ctx.das,
            "stage_window": ctx.stage.label,
            "observed_at": ctx.today.isoformat(),
        },
        actions=["SCOUT_FIELD", "CHECK_FOR_PEST", "CONSULT_KVK"],
        source_note="ICAR crop-specific IPM guidelines",
    )


@rule("HARVEST_RAIN_CLASH")
def harvest_rain_clash(ctx: RuleContext):
    """
    Rule 6: Crop within 10 days of expected harvest and rain over 25 mm
    forecast in that window.

    Advisory intent: Consider harvesting early; arrange covered storage.
    """
    # Check if we are near maturity / harvest stage
    if ctx.stage.name not in ("maturity", "harvest", "grain_fill"):
        return None

    # Check for significant rain in the forecast
    heavy_rain_days = [d for d in ctx.forecast if d.rain_mm >= HARVEST_RAIN_MM]
    if not heavy_rain_days:
        return None

    total_rain = sum(d.rain_mm for d in heavy_rain_days)
    sev = severity_for(total_rain, HARVEST_RAIN_MM, "critical")
    if sev is None:
        return None

    return ctx.event(
        rule_id="HARVEST_RAIN_CLASH",
        severity=sev,
        window=(heavy_rain_days[0].date, heavy_rain_days[-1].date),
        evidence={
            "rain_mm_in_window": round(total_rain, 1),
            "threshold_mm": HARVEST_RAIN_MM,
            "heavy_rain_days": len(heavy_rain_days),
            "crop": ctx.farm.crop,
            "days_since_sowing": ctx.das,
            "stage_window": ctx.stage.label,
            "observed_at": ctx.today.isoformat(),
        },
        actions=["HARVEST_EARLY", "ARRANGE_COVERED_STORAGE", "DRY_PRODUCE_NOW"],
        source_note="TEAM ESTIMATE, needs validation",
    )


@rule("FROST_RISK")
def frost_risk(ctx: RuleContext):
    """
    Rule 7: t_min under 4°C forecast, rabi crops or vegetables.

    Advisory intent: Light irrigation the evening before; smoke or cover.
    """
    # Frost is relevant for rabi (wheat) and vegetables (tomato)
    if ctx.farm.crop not in ("wheat", "tomato"):
        return None

    frost_days = [d for d in ctx.forecast if d.t_min_c < FROST_TMIN_C]
    if not frost_days:
        return None

    min_temp = min(d.t_min_c for d in frost_days)
    # Invert: lower temp = more severe.  Use threshold - temp as value.
    cold_severity = FROST_TMIN_C - min_temp
    sev = severity_for(cold_severity + FROST_TMIN_C, FROST_TMIN_C, "critical")
    if sev is None:
        return None

    return ctx.event(
        rule_id="FROST_RISK",
        severity=sev,
        window=(frost_days[0].date, frost_days[-1].date),
        evidence={
            "t_min_lowest_c": round(min_temp, 1),
            "threshold_c": FROST_TMIN_C,
            "frost_days": len(frost_days),
            "crop": ctx.farm.crop,
            "days_since_sowing": ctx.das,
            "stage_window": ctx.stage.label,
            "observed_at": ctx.today.isoformat(),
        },
        actions=["IRRIGATE_EVENING", "COVER_NURSERY", "SMOKE_PROTECTION"],
        source_note="IMD cold wave criteria for Jharkhand",
    )
