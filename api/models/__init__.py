"""
Canonical data models — Section 11 of the build spec.

Every object that crosses a boundary (API, database, rules engine) is one of
these Pydantic models.  No component downstream of ingestion ever sees a raw
provider payload.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 11.1  WeatherDay — normalised daily weather record
# ---------------------------------------------------------------------------
class WeatherDay(BaseModel):
    grid_id: str  # e.g. "HZB-01"
    date: date
    t_max_c: float
    t_min_c: float
    rain_mm: float  # 24h total
    rain_prob: float = Field(ge=0.0, le=1.0)  # 0..1
    humidity_pct: float  # daily mean relative humidity
    wind_kph_max: float
    soil_moisture_0_7cm: float | None = None
    source: str = "open-meteo"
    fetched_at: datetime = Field(default_factory=datetime.now)

    @field_validator("t_max_c", "t_min_c")
    @classmethod
    def temp_range(cls, v: float) -> float:
        if not -10 <= v <= 55:
            raise ValueError(f"Temperature {v} out of valid range [-10, 55]")
        return v

    @field_validator("rain_mm")
    @classmethod
    def rain_range(cls, v: float) -> float:
        if not 0 <= v <= 500:
            raise ValueError(f"Rainfall {v} out of valid range [0, 500]")
        return v

    @field_validator("humidity_pct")
    @classmethod
    def humidity_clamp(cls, v: float) -> float:
        return max(0.0, min(100.0, v))


# ---------------------------------------------------------------------------
# 11.2  Farm
# ---------------------------------------------------------------------------
SUPPORTED_CROPS = ("paddy", "maize", "wheat", "tomato")
IRRIGATION_TYPES = ("rainfed", "canal", "borewell", "mixed")
SUPPORTED_LANGUAGES = ("hi", "en", "kho", "bn")


class Farm(BaseModel):
    farm_id: str
    owner_uid: str  # Firebase Auth uid
    village: str
    grid_id: str  # resolved from lat/lon at creation
    lat: float
    lon: float
    crop: Literal["paddy", "maize", "wheat", "tomato"]
    sowing_date: date
    area_ha: float = Field(gt=0)
    irrigation: Literal["rainfed", "canal", "borewell", "mixed"]
    language: Literal["hi", "en", "kho", "bn"] = "hi"
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)


class FarmCreate(BaseModel):
    """Request body for POST /api/v1/farms."""

    village: str
    lat: float
    lon: float
    crop: Literal["paddy", "maize", "wheat", "tomato"]
    sowing_date: date
    area_ha: float = Field(gt=0)
    irrigation: Literal["rainfed", "canal", "borewell", "mixed"] = "rainfed"
    language: Literal["hi", "en", "kho", "bn"] = "hi"

    @field_validator("sowing_date")
    @classmethod
    def validate_sowing(cls, v: date) -> date:
        today = date.today()
        if (today - v).days > 365:
            raise ValueError("Sowing date is more than 365 days ago.")
        if (v - today).days > 30:
            raise ValueError("Sowing date is more than 30 days in the future.")
        return v


class FarmUpdate(BaseModel):
    """Request body for PATCH /api/v1/farms/{farm_id}."""

    crop: Literal["paddy", "maize", "wheat", "tomato"] | None = None
    sowing_date: date | None = None
    language: Literal["hi", "en", "kho", "bn"] | None = None
    irrigation: Literal["rainfed", "canal", "borewell", "mixed"] | None = None


class FarmResponse(BaseModel):
    farm_id: str
    grid_id: str
    growth_stage: str
    days_after_sowing: int
    created_at: datetime


# ---------------------------------------------------------------------------
# 11.3  RiskEvent — the boundary between deterministic and generative code
# ---------------------------------------------------------------------------
class RiskEvent(BaseModel):
    event_id: str  # deterministic hash
    farm_id: str
    rule_id: str  # e.g. "HEAVY_RAIN_PRE_SPRAY"
    severity: Literal["LOW", "MODERATE", "SEVERE"]
    window_start: date
    window_end: date
    crop: str
    growth_stage: str
    evidence: dict  # the exact numbers that fired the rule
    recommended_actions: list[str]  # canonical English action keys
    source_note: str  # which advisory source the threshold is from
    created_at: datetime = Field(default_factory=datetime.now)

    @staticmethod
    def make_event_id(farm_id: str, rule_id: str, window_start: date) -> str:
        """Deterministic hash — re-running the job the same day cannot duplicate alerts."""
        raw = f"{farm_id}|{rule_id}|{window_start.isoformat()}"
        return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# 11.4  Advisory — what the farmer receives
# ---------------------------------------------------------------------------
class Advisory(BaseModel):
    advisory_id: str  # "{event_id}_{lang}"
    event_id: str
    farm_id: str
    language: str
    severity: Literal["LOW", "MODERATE", "SEVERE"]
    rule_id: str
    headline: str  # <= 60 chars
    body: str  # <= 320 chars
    actions: list[str]  # exactly 3, each <= 90 chars
    spoken_script: str  # <= 55 words, natural read aloud
    generated_by: Literal["gemini", "template"]
    model_version: str | None = None
    read: bool = False
    window_start: date | None = None
    window_end: date | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class AdvisoryDetail(Advisory):
    """Full advisory with evidence for the 'Kya hua?' screen."""

    evidence: dict = {}
    source_note: str = ""
    forecast_used: list[dict] = []


class AdvisoryListResponse(BaseModel):
    farm_id: str
    count: int
    advisories: list[Advisory]


# ---------------------------------------------------------------------------
# Ask (Bolo Kisan)
# ---------------------------------------------------------------------------
class AskRequest(BaseModel):
    farm_id: str
    question: str
    language: Literal["hi", "en", "kho", "bn"] = "hi"


class AskResponse(BaseModel):
    answer_text: str
    spoken_script: str
    grounded: bool
    used_context: list[str] = []
    confidence_note: str | None = None


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------
class FeedbackCreate(BaseModel):
    advisory_id: str
    farm_id: str
    helpful: bool
    acted: bool = False
    comment: str | None = None


# ---------------------------------------------------------------------------
# Error envelope — Section 18.6
# ---------------------------------------------------------------------------
class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Growth Stage
# ---------------------------------------------------------------------------
class GrowthStage(BaseModel):
    """A crop's current growth stage, derived from days-after-sowing."""

    name: str
    das_start: int
    das_end: int
    das_current: int
    sensitive_water: str = "low"
    sensitive_heat: str = "low"
    sensitive_pest: str = "low"
    input_window: bool = False

    @property
    def label(self) -> str:
        return f"{self.name} ({self.das_start}-{self.das_end} DAS)"

    def near_input_window(self, days: int = 7) -> bool:
        """True if the crop is within `days` of an input window stage."""
        return self.input_window

    def sensitivity(self, factor: str) -> str:
        """Return sensitivity level for a given factor."""
        return getattr(self, f"sensitive_{factor}", "low")


# Pre-defined sentinel stages
PRE_SOWING = GrowthStage(
    name="pre_sowing", das_start=-999, das_end=-1, das_current=-1
)
POST_HARVEST = GrowthStage(
    name="post_harvest", das_start=9000, das_end=9999, das_current=9999
)
