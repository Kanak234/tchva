"""
Alert fatigue.

Every rule in this file is correct in the narrow sense — the condition it
describes really is present. These tests are about the second question,
the one that decides whether the product works: how often does a farmer
get told about it, and at what severity.

A SEVERE alert that arrives every morning all monsoon is worse than no
alert, because the farmer stops opening the app and misses the flood
warning too.
"""

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import RiskEvent  # noqa: E402
from rules.definitions import (  # noqa: E402
    PEST_HUMIDITY_PCT,
    PEST_TMIN_BANDS,
    week_anchor,
)


class TestWeekAnchor:
    def test_monday_anchors_to_itself(self):
        monday = date(2026, 8, 17)
        assert monday.weekday() == 0
        assert week_anchor(monday) == monday

    def test_every_day_of_a_week_shares_an_anchor(self):
        monday = date(2026, 8, 17)
        anchors = {week_anchor(monday + timedelta(days=i)) for i in range(7)}
        assert anchors == {monday}

    def test_next_week_gets_a_new_anchor(self):
        assert week_anchor(date(2026, 8, 24)) != week_anchor(date(2026, 8, 23))


class TestAdvisoryIsNotReissuedDaily:
    """
    event_id is a hash of (farm_id, rule_id, window_start), and
    save_advisory upserts on advisory_id. So a stable window_start means
    the advisory is refreshed in place rather than multiplying.
    """

    @pytest.mark.parametrize("rule_id", ["PEST_WEATHER_WINDOW", "DRY_SPELL"])
    def test_one_event_id_per_week(self, rule_id):
        ids = {
            RiskEvent.make_event_id(
                "farm_1", rule_id, week_anchor(date(2026, 8, 17) + timedelta(days=i))
            )
            for i in range(7)
        }
        assert len(ids) == 1, "a persistent condition must not re-alert daily"

    @pytest.mark.parametrize("rule_id", ["PEST_WEATHER_WINDOW", "DRY_SPELL"])
    def test_a_new_week_does_re_alert(self, rule_id):
        """Suppression must not be permanent — the condition still matters."""
        this_week = RiskEvent.make_event_id(
            "farm_1", rule_id, week_anchor(date(2026, 8, 21))
        )
        next_week = RiskEvent.make_event_id(
            "farm_1", rule_id, week_anchor(date(2026, 8, 28))
        )
        assert this_week != next_week

    def test_sliding_window_would_have_alerted_daily(self):
        """
        Documents the behaviour being fixed: anchoring on `today` produced
        a distinct event id, and therefore a distinct advisory, every day.
        """
        ids = {
            RiskEvent.make_event_id(
                "farm_1", "PEST_WEATHER_WINDOW", date(2026, 8, 17) + timedelta(days=i)
            )
            for i in range(7)
        }
        assert len(ids) == 7


class TestPestRuleOnOrdinaryMonsoonWeather:
    """
    Hazaribagh monsoon nights sit at 24-26C. The paddy band is 20-30C, a
    full ten degrees wide, and monsoon humidity is above 85% most days.
    The rule's trigger condition is therefore satisfied by the season
    itself, not by any pest signal.
    """

    MONSOON = [(88, 24.5), (91, 25.0), (87, 24.8), (93, 25.2),
               (89, 24.1), (90, 25.5), (86, 24.9)]

    def test_ordinary_monsoon_satisfies_the_trigger(self):
        band = PEST_TMIN_BANDS["paddy"]
        hits = [
            1
            for h, t in self.MONSOON
            if h >= PEST_HUMIDITY_PCT and band[0] <= t <= band[1]
        ]
        assert sum(hits) == 7, (
            "If this ever stops being 7, the thresholds were retuned — "
            "check that the rule now describes a departure from normal."
        )

    def test_paddy_band_is_wide_enough_to_swallow_the_season(self):
        low, high = PEST_TMIN_BANDS["paddy"]
        assert high - low >= 10
