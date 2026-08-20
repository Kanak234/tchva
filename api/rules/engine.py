"""
Rules Engine — Section 16 of the build spec.

The most important module in the repository.

Pure Python, no network calls, no database access, no AI.
Given the same inputs it always produces the same outputs.

Each rule is a function registered via the @rule decorator.
Adding a rule = adding one function + one table row.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from models import Farm, GrowthStage, RiskEvent, WeatherDay

logger = logging.getLogger("fasal_kavach.rules")

# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------
_RULES: dict[str, Callable] = {}


def rule(rule_id: str):
    """Decorator to register a rule function."""

    def decorator(fn: Callable):
        _RULES[rule_id] = fn
        fn.rule_id = rule_id
        return fn

    return decorator


# ---------------------------------------------------------------------------
# Rule context — convenience wrapper passed to each rule
# ---------------------------------------------------------------------------
@dataclass
class RuleContext:
    farm: Farm
    forecast: list[WeatherDay]
    stage: GrowthStage
    baselines: dict
    today: date

    @property
    def das(self) -> int:
        return self.stage.das_current

    def baseline(self, key: str) -> float:
        """Look up a baseline value for this grid cell and week of year."""
        grid_data = self.baselines.get(self.farm.grid_id, {})
        weeks = grid_data.get("weeks", {})
        week = str(self.today.isocalendar()[1])
        week_data = weeks.get(week, {})
        return float(week_data.get(key, 0.0))

    def event(
        self,
        rule_id: str,
        severity: str,
        window: tuple[date, date],
        evidence: dict,
        actions: list[str],
        source_note: str,
    ) -> RiskEvent:
        """Build a RiskEvent with a deterministic event_id."""
        event_id = RiskEvent.make_event_id(self.farm.farm_id, rule_id, window[0])
        return RiskEvent(
            event_id=event_id,
            farm_id=self.farm.farm_id,
            rule_id=rule_id,
            severity=severity,
            window_start=window[0],
            window_end=window[1],
            crop=self.farm.crop,
            growth_stage=self.stage.label,
            evidence=evidence,
            recommended_actions=actions,
            source_note=source_note,
        )


# ---------------------------------------------------------------------------
# Severity assignment — Section 16.3
#
# Severity is a function of how far past the threshold we are and how
# sensitive the growth stage is.  Never chosen by the AI.
# ---------------------------------------------------------------------------
def severity_for(
    value: float, threshold: float, stage_sensitivity: str
) -> str | None:
    if threshold == 0:
        return None
    ratio = value / threshold
    if stage_sensitivity == "critical":
        if ratio >= 1.5:
            return "SEVERE"
        if ratio >= 1.0:
            return "MODERATE"
        if ratio >= 0.8:
            return "LOW"
    else:
        if ratio >= 2.0:
            return "SEVERE"
        if ratio >= 1.3:
            return "MODERATE"
        if ratio >= 1.0:
            return "LOW"
    return None


# ---------------------------------------------------------------------------
# The public interface — Section 16.1
# ---------------------------------------------------------------------------
def evaluate(
    farm: Farm,
    forecast: list[WeatherDay],
    stage: GrowthStage,
    baselines: dict,
    today: date,
) -> list[RiskEvent]:
    """
    Pure function.  No I/O.  Deterministic.

    Runs every registered rule against the given context and collects
    all non-None RiskEvents.
    """
    if not forecast:
        return []

    ctx = RuleContext(
        farm=farm,
        forecast=forecast,
        stage=stage,
        baselines=baselines,
        today=today,
    )

    events: list[RiskEvent] = []
    for rule_id, rule_fn in _RULES.items():
        try:
            result = rule_fn(ctx)
            if result is not None:
                events.append(result)
        except Exception:
            logger.exception(f"Rule {rule_id} raised for farm {farm.farm_id}")
            # Per-farm try/except — one bad record must not kill the batch

    return events


# ---------------------------------------------------------------------------
# Import the rule definitions so they register themselves
# ---------------------------------------------------------------------------
from rules import definitions  # noqa: E402, F401
