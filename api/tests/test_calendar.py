"""
Crop Calendar Tests — Section 28

Tests on stage boundaries and edge cases from Section 17.3.
"""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rules.crop_calendar import stage_for


class TestStageFor:
    def test_paddy_nursery(self):
        """DAS 0-21 -> nursery."""
        stage = stage_for("paddy", date(2026, 7, 15), date(2026, 7, 20))
        assert stage.name == "nursery"
        assert stage.das_current == 5

    def test_paddy_flowering(self):
        """DAS 56-75 -> flowering."""
        stage = stage_for("paddy", date(2026, 7, 15), date(2026, 9, 10))
        assert stage.name == "flowering"

    def test_paddy_maturity(self):
        """DAS 101-120 -> maturity."""
        stage = stage_for("paddy", date(2026, 7, 15), date(2026, 10, 30))
        assert stage.name == "maturity"

    def test_pre_sowing(self):
        """Sowing date in the future -> PRE_SOWING."""
        stage = stage_for("paddy", date(2026, 9, 1), date(2026, 8, 18))
        assert stage.name == "pre_sowing"
        assert stage.das_current < 0

    def test_post_harvest(self):
        """DAS beyond the last stage -> POST_HARVEST."""
        stage = stage_for("paddy", date(2026, 1, 1), date(2026, 8, 18))
        assert stage.name == "post_harvest"

    def test_maize_tasseling(self):
        """DAS 36-60 for maize -> tasseling."""
        stage = stage_for("maize", date(2026, 7, 10), date(2026, 8, 18))
        assert stage.name == "tasseling"
        assert stage.sensitive_water == "critical"

    def test_wheat_germination(self):
        """DAS 0-20 for wheat -> germination."""
        stage = stage_for("wheat", date(2026, 11, 15), date(2026, 11, 25))
        assert stage.name == "germination"

    def test_tomato_flowering(self):
        """DAS 46-65 for tomato -> flowering."""
        stage = stage_for("tomato", date(2026, 7, 1), date(2026, 8, 18))
        assert stage.name == "flowering"
        assert stage.sensitive_heat == "critical"

    def test_unknown_crop(self):
        """Unsupported crop -> post_harvest (reject at API level)."""
        stage = stage_for("sugarcane", date(2026, 7, 1), date(2026, 8, 18))
        assert stage.name == "post_harvest"

    def test_stage_sensitivity(self):
        """Sensitivity values are accessible."""
        stage = stage_for("paddy", date(2026, 7, 15), date(2026, 9, 10))
        assert stage.sensitivity("water") in ("low", "medium", "high", "critical")
        assert stage.sensitivity("heat") in ("low", "medium", "high", "critical")

    def test_boundary_das_start(self):
        """Exactly at das_start of a stage."""
        stage = stage_for("paddy", date(2026, 7, 15), date(2026, 9, 9))
        _das = (date(2026, 9, 9) - date(2026, 7, 15)).days  # 56
        assert stage.name == "flowering"

    def test_boundary_das_end(self):
        """Exactly at das_end of a stage."""
        stage = stage_for("paddy", date(2026, 7, 15), date(2026, 9, 28))
        _das = (date(2026, 9, 28) - date(2026, 7, 15)).days  # 75
        assert stage.name == "flowering"
