"""
AI Schema Validation Tests — Section 28.4

Tests the post-generation validation gates.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai.client import (
    ask_question,
    extract_numbers,
    generate_advisory,
    get_ai_backend,
    validate_advisory,
)


class TestValidateAdvisory:
    def test_valid_advisory_passes(self):
        result = {
            "headline": "Heavy rain in next 2 days",
            "body": "61.4 mm rain expected. Do not spray urea.",
            "actions": ["Delay spray", "Clear drains", "Reschedule urea"],
            "spoken_script": "Heavy rain coming. Do not spray.",
        }
        event = {
            "evidence": {"rain_mm_next_48h": 61.4, "threshold_mm": 40.0},
        }
        assert validate_advisory(result, event) is True

    def test_missing_field_fails(self):
        result = {
            "headline": "Test",
            "body": "Test body",
            # missing "actions" and "spoken_script"
        }
        assert validate_advisory(result, {}) is False

    def test_wrong_action_count_fails(self):
        result = {
            "headline": "Test",
            "body": "Test body",
            "actions": ["Only one action"],
            "spoken_script": "Test",
        }
        assert validate_advisory(result, {}) is False

    def test_hallucinated_number_fails(self):
        result = {
            "headline": "Rain alert",
            "body": "Expected 999 mm of rain tomorrow",
            "actions": ["Act 1", "Act 2", "Act 3"],
            "spoken_script": "999 mm rain coming",
        }
        event = {
            "evidence": {"rain_mm_next_48h": 61.4},
        }
        assert validate_advisory(result, event) is False

    def test_banned_pesticide_fails(self):
        result = {
            "headline": "Pest alert",
            "body": "Apply carbendazim 2g per litre immediately",
            "actions": ["Apply carbendazim", "Spray now", "Check field"],
            "spoken_script": "Apply carbendazim spray",
        }
        event = {"evidence": {}}
        assert validate_advisory(result, event) is False

    def test_dosage_pattern_fails(self):
        result = {
            "headline": "Pest alert",
            "body": "Apply 50 ml per litre of water",
            "actions": ["Spray 50 ml", "Check field", "Consult KVK"],
            "spoken_script": "Apply spray at 50 ml rate",
        }
        event = {"evidence": {"rate": 50}}
        assert validate_advisory(result, event) is False


class TestExtractNumbers:
    def test_integers(self):
        assert 42 in extract_numbers("It will rain 42 mm")

    def test_floats(self):
        assert 61.4 in extract_numbers("Expected 61.4 mm rain")

    def test_no_numbers(self):
        assert extract_numbers("No numbers here") == set()

    def test_negative(self):
        assert -2 in extract_numbers("Temperature will drop to -2 degrees")


class TestAIBackendLadder:
    def test_get_ai_backend_ollama(self):
        with patch("ai.client.USE_OLLAMA", True):
            assert get_ai_backend() == "ollama"

    def test_get_ai_backend_gemini(self):
        with patch("ai.client.USE_OLLAMA", False), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
            assert get_ai_backend() == "gemini"

    def test_get_ai_backend_template(self):
        with patch("ai.client.USE_OLLAMA", False), \
             patch.dict(os.environ, {}):
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]
            assert get_ai_backend() == "template"

    @pytest.mark.asyncio
    async def test_generate_advisory_template_fallback(self):
        with patch("ai.client.get_ai_backend", return_value="template"):
            result = await generate_advisory({"evidence": {}}, "en")
            assert result is None

    @pytest.mark.asyncio
    async def test_ask_question_template_fallback(self):
        with patch("ai.client.get_ai_backend", return_value="template"):
            result = await ask_question("any question", "en", {})
            assert result["grounded"] is False
            assert "I do not have that information" in result["answer_text"]
