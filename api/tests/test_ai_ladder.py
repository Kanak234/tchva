"""
Backend ladder, Groq transport, and the number-containment gate.

The gate tests matter most. Everything else in this project is designed
so that a farmer is never told a number the rules engine did not produce,
and these are the tests that hold that line.
"""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai import client as ai_client  # noqa: E402
from ai.client import (  # noqa: E402
    _parse_json,
    _to_ascii_digits,
    extract_numbers,
    generate_advisory,
    get_backend_ladder,
    validate_advisory,
)


def _clear_ai_env(monkeypatch):
    for key in ("AI_BACKENDS", "GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(key, raising=False)


class TestBackendLadder:
    def test_explicit_env_wins(self, monkeypatch):
        _clear_ai_env(monkeypatch)
        monkeypatch.setenv("AI_BACKENDS", "gemini, template")
        assert get_backend_ladder() == ["gemini", "template"]

    def test_groq_precedes_gemini(self, monkeypatch):
        _clear_ai_env(monkeypatch)
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        monkeypatch.setenv("GEMINI_API_KEY", "gem_test")
        with patch.object(ai_client, "USE_OLLAMA", False):
            assert get_backend_ladder() == ["groq", "gemini", "template"]

    def test_ollama_override_goes_first(self, monkeypatch):
        _clear_ai_env(monkeypatch)
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        with patch.object(ai_client, "USE_OLLAMA", True):
            assert get_backend_ladder()[0] == "ollama"

    def test_template_is_always_last(self, monkeypatch):
        _clear_ai_env(monkeypatch)
        with patch.object(ai_client, "USE_OLLAMA", False):
            assert get_backend_ladder() == ["template"]


class TestLadderFallthrough:
    """A dead backend must not sink the request."""

    @pytest.mark.asyncio
    async def test_falls_through_to_next_backend(self, monkeypatch):
        _clear_ai_env(monkeypatch)
        monkeypatch.setenv("AI_BACKENDS", "groq,gemini,template")

        good = {
            "headline": "Heavy rain coming",
            "body": "61.4 mm expected. Do not spray.",
            "actions": ["Delay spray", "Clear drains", "Wait"],
            "spoken_script": "Heavy rain coming. Do not spray.",
        }
        event = {"evidence": {"rain_mm_next_48h": 61.4}}

        async def fake_backend(backend, system, prompt, schema):
            if backend == "groq":
                raise RuntimeError("groq is down")
            return '{"headline": "Heavy rain coming", ' \
                   '"body": "61.4 mm expected. Do not spray.", ' \
                   '"actions": ["Delay spray", "Clear drains", "Wait"], ' \
                   '"spoken_script": "Heavy rain coming. Do not spray."}'

        with patch.object(ai_client, "_call_backend", side_effect=fake_backend):
            result = await generate_advisory(event, "en")

        assert result is not None
        assert result["generated_by"] == "gemini"
        assert result["headline"] == good["headline"]

    @pytest.mark.asyncio
    async def test_all_backends_dead_returns_none(self, monkeypatch):
        _clear_ai_env(monkeypatch)
        monkeypatch.setenv("AI_BACKENDS", "groq,gemini,template")

        with patch.object(
            ai_client, "_call_backend", side_effect=RuntimeError("no")
        ):
            assert await generate_advisory({"evidence": {}}, "en") is None

    @pytest.mark.asyncio
    async def test_invalid_output_falls_through(self, monkeypatch):
        """A backend that answers but hallucinates does not win the race."""
        _clear_ai_env(monkeypatch)
        monkeypatch.setenv("AI_BACKENDS", "groq,template")

        with patch.object(
            ai_client,
            "_call_backend",
            new=AsyncMock(
                return_value='{"headline": "Rain", "body": "Expect 999 mm", '
                '"actions": ["a", "b", "c"], "spoken_script": "999 mm"}'
            ),
        ):
            result = await generate_advisory(
                {"evidence": {"rain_mm_next_48h": 61.4}}, "en"
            )

        assert result is None


class TestGroqTransport:
    @pytest.mark.asyncio
    async def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            await ai_client.call_groq("sys", "prompt", format_json=True)


class TestDevanagariNumberGate:
    """
    Pins the containment gate's behaviour on non-ASCII numerals.

    These pass on the old code too — CPython's float() already parses
    Devanagari digits. That is worth a test precisely because nothing
    stated it: the gate's correctness in Hindi and Bengali was resting on
    an undocumented parsing convenience. Now it is pinned.
    """

    def test_devanagari_digits_fold_to_ascii(self):
        assert _to_ascii_digits("५० किलो") == "50 किलो"

    def test_bengali_digits_fold_to_ascii(self):
        assert _to_ascii_digits("৭৫ মিমি") == "75 মিমি"

    def test_devanagari_numbers_are_extracted(self):
        assert 50.0 in extract_numbers("५० किलो यूरिया डालें")

    def test_hallucinated_devanagari_number_is_rejected(self):
        result = {
            "headline": "बारिश की चेतावनी",
            "body": "खेत में ९९९ मिमी बारिश होगी।",
            "actions": ["नाली साफ करें", "छिड़काव रोकें", "इंतज़ार करें"],
            "spoken_script": "बहुत बारिश आ रही है।",
        }
        event = {"evidence": {"rain_mm_next_48h": 61.4}}
        assert validate_advisory(result, event) is False

    def test_grounded_devanagari_number_is_accepted(self):
        result = {
            "headline": "बारिश की चेतावनी",
            "body": "अगले दो दिन में ६१.४ मिमी बारिश होगी।",
            "actions": ["नाली साफ करें", "छिड़काव रोकें", "इंतज़ार करें"],
            "spoken_script": "बारिश आ रही है।",
        }
        event = {"evidence": {"rain_mm_next_48h": 61.4}}
        assert validate_advisory(result, event) is True

    def test_devanagari_dosage_is_rejected(self):
        result = {
            "headline": "छिड़काव",
            "body": "५० ml प्रति लीटर डालें।",
            "actions": ["छिड़कें", "जाँचें", "पूछें"],
            "spoken_script": "छिड़काव करें।",
        }
        assert validate_advisory(result, {"evidence": {"rate": 50}}) is False


class TestJsonParsing:
    def test_plain_json(self):
        assert _parse_json('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        assert _parse_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_bare_fence(self):
        assert _parse_json('```\n{"a": 1}\n```') == {"a": 1}


class TestDatesAreNotHallucinations:
    """
    Regression: the gate rejected correct advisories for citing their own
    window. "2026-08-22" was read as 2026, -8, -22, so the context held
    negative day numbers while the model, writing the dates in prose,
    produced positive ones. Every advisory that mentioned its window was
    thrown away and the ladder fell to the template.

    Only a live API call surfaced this — the mocked tests used clean
    numbers and never included a date.
    """

    EVENT = {
        "crop": "paddy",
        "window_start": "2026-08-22",
        "window_end": "2026-08-24",
        "evidence": {"rain_mm_next_48h": 61.4, "threshold_mm": 40.0},
    }

    def test_iso_date_yields_positive_components(self):
        nums = extract_numbers("2026-08-22")
        assert nums == {2026.0, 8.0, 22.0}

    def test_day_month_year_order_too(self):
        assert extract_numbers("22-08-2026") == {22.0, 8.0, 2026.0}

    def test_advisory_may_cite_its_own_window(self):
        result = {
            "headline": "भारी बारिश की चेतावनी",
            "body": "22 अगस्त से 24 अगस्त तक 61.4 मिमी बारिश का अनुमान है।",
            "actions": ["छिड़काव रोकें", "नाली साफ करें", "इंतज़ार करें"],
            "spoken_script": "भारी बारिश आ रही है।",
        }
        assert validate_advisory(result, self.EVENT) is True

    def test_genuine_negatives_still_parse(self):
        """The lookbehind must not break sub-zero temperatures."""
        assert extract_numbers("तापमान -5.5 डिग्री") == {-5.5}
        assert extract_numbers("low of -2 C") == {-2.0}

    def test_invented_number_is_still_caught(self):
        """The fix must not turn the gate off."""
        result = {
            "headline": "बारिश",
            "body": "22 अगस्त को 999 मिमी बारिश होगी।",
            "actions": ["a", "b", "c"],
            "spoken_script": "बारिश।",
        }
        assert validate_advisory(result, self.EVENT) is False


class TestPromptCarriesTheSchema:
    """
    Only Gemini accepts a response_schema. Groq and Ollama are told the
    shape in words, and if that hint ever stops matching what
    validate_advisory() requires, every advisory from those backends is
    rejected for a missing field while the request still returns 200 —
    a silent fall to the template with a healthy-looking log.
    """

    def test_hint_names_every_required_advisory_field(self):
        hint = ai_client._schema_hint(ai_client.ADVISORY_SCHEMA)
        for field in ("headline", "body", "actions", "spoken_script"):
            assert f'"{field}"' in hint

    def test_hint_names_every_required_ask_field(self):
        hint = ai_client._schema_hint(ai_client.ASK_SCHEMA)
        for field in ("answer_text", "spoken_script", "grounded"):
            assert f'"{field}"' in hint

    def test_hint_shows_three_actions(self):
        """validate_advisory() demands exactly 3, so the prompt must say 3."""
        hint = ai_client._schema_hint(ai_client.ADVISORY_SCHEMA)
        assert hint.count("string") >= 3
        assert "[string, string, string]" in hint

    @pytest.mark.asyncio
    async def test_groq_and_ollama_receive_the_hint(self, monkeypatch):
        seen = {}

        async def fake(system, prompt, format_json):
            seen[system] = True
            return "{}"

        monkeypatch.setattr(ai_client, "call_groq", fake)
        monkeypatch.setattr(ai_client, "call_ollama", fake)
        for backend in ("groq", "ollama"):
            seen.clear()
            await ai_client._call_backend(
                backend, "SYS", "PROMPT", ai_client.ADVISORY_SCHEMA
            )
            system_sent = next(iter(seen))
            assert "headline" in system_sent, f"{backend} was not told the schema"

    @pytest.mark.asyncio
    async def test_gemini_does_not_get_the_hint(self, monkeypatch):
        """It gets a real response_schema instead; duplicating it wastes tokens."""
        seen = {}

        async def fake_gemini(system, prompt, schema):
            seen["system"] = system
            return "{}"

        monkeypatch.setattr(ai_client, "call_gemini", fake_gemini)
        await ai_client._call_backend(
            "gemini", "SYS", "PROMPT", ai_client.ADVISORY_SCHEMA
        )
        assert seen["system"] == "SYS"


class TestStageNamesAreLocalised:
    """
    The stage arrives as an English slug from crop_calendar.csv. Passed
    through raw it reappeared inside Hindi advisories — "अभी vegetative
    stage में है" — which reads as broken to the person the app is for.
    """

    def test_hindi_stage_is_translated(self):
        assert ai_client.stage_name("vegetative", "hi") == "बढ़वार"

    def test_case_and_spacing_are_tolerated(self):
        """Events carry 'VEGETATIVE'; the calendar writes 'vegetative'."""
        assert ai_client.stage_name("VEGETATIVE", "hi") == "बढ़वार"
        assert ai_client.stage_name("grain fill", "hi") == "दाना भरना"

    def test_english_keeps_the_readable_slug(self):
        assert ai_client.stage_name("grain_fill", "en") == "grain fill"

    def test_unknown_stage_degrades_to_readable_text(self):
        """A new stage in the CSV must not crash or print an underscore."""
        assert ai_client.stage_name("pod_setting", "hi") == "pod setting"

    def test_every_calendar_stage_has_all_languages(self):
        for stage, names in ai_client.STAGE_NAMES.items():
            for lang in ("hi", "kho", "bn"):
                assert names.get(lang), f"{stage} is missing {lang}"

    def test_context_block_carries_the_local_name(self):
        block = ai_client.build_context_block(
            {"crop": "paddy", "growth_stage": "VEGETATIVE"}, "hi"
        )
        assert "बढ़वार" in block
        assert "vegetative" not in block


class TestPromptPhrasesAreLocalised:
    """
    Any literal the prompt tells the model to output must be supplied in
    the target language. Rule 3 once read: Say "consult your KVK or
    agri-dealer". The model obeyed exactly — in English, in the middle of
    Hindi. Instructing a model to translate a quoted string is unreliable;
    handing it the right string is not.
    """

    LANGS = ("hi", "en", "kho", "bn")

    def test_kvk_phrase_covers_every_language(self):
        for lang in self.LANGS:
            assert ai_client.KVK_PHRASE.get(lang)

    def test_no_info_phrase_covers_every_language(self):
        for lang in self.LANGS:
            assert ai_client.NO_INFO_PHRASE.get(lang)

    def test_hindi_advisory_prompt_carries_no_english_kvk_text(self):
        prompt = ai_client.ADVISORY_SYSTEM.format(
            language="Hindi", kvk_phrase=ai_client.KVK_PHRASE["hi"]
        )
        assert "consult your KVK" not in prompt
        assert "अपने KVK या कृषि दुकानदार से सलाह लें" in prompt

    def _ask_prompt(self, lang: str, lang_name: str) -> str:
        return ai_client.ASK_SYSTEM.format(
            language_rule=ai_client._language_rule(lang_name, lang),
            kvk_phrase=ai_client.KVK_PHRASE[lang],
            no_info_phrase=ai_client.NO_INFO_PHRASE[lang],
        )

    def test_hindi_ask_prompt_carries_no_english_fallback_text(self):
        prompt = self._ask_prompt("hi", "Hindi")
        assert "I do not have that information" not in prompt
        assert "कृपया अपने नजदीकी KVK से पूछें" in prompt

    def test_kvk_line_is_an_addition_not_a_replacement(self):
        """
        Regression: the prompt once said "If asked about treatment, write
        exactly: <phrase>". A spray question is a treatment question, so
        the model returned the phrase as the entire answer and nothing
        else. It must be told to answer first and append the phrase.
        """
        prompt = self._ask_prompt("en", "English")
        assert "do not send it on its own" in prompt

    def test_english_language_rule_is_not_self_contradictory(self):
        """It used to read: write every word in English, leave no English."""
        rule = ai_client._language_rule("English", "en")
        assert "Leave no English" not in rule
        assert "no English in the output" not in rule

    def test_non_english_rule_still_forbids_english(self):
        rule = ai_client._language_rule("Bengali", "bn")
        assert "Bengali" in rule
        assert "no English" in rule

    def test_fallback_response_uses_the_same_table(self):
        """One source for the phrase, so prompt and fallback cannot diverge."""
        for lang in self.LANGS:
            assert (
                ai_client._ungrounded_response(lang)["answer_text"]
                == ai_client.NO_INFO_PHRASE[lang]
            )

    def test_unknown_language_falls_back_to_english(self):
        assert ai_client._ungrounded_response("ta")["answer_text"] == (
            ai_client.NO_INFO_PHRASE["en"]
        )


class TestCropNamesAreLocalised:
    """
    Bengali output rendered paddy as "প্যাডিতে" — a transliteration of
    the English word rather than ধান, the actual crop. Same cause as the
    stage slugs: the crop reached the prompt as the English key from
    crop_calendar.csv.
    """

    def test_bengali_paddy(self):
        assert ai_client.crop_name("paddy", "bn") == "ধান"

    def test_hindi_maize(self):
        assert ai_client.crop_name("maize", "hi") == "मक्का"

    def test_english_keeps_the_slug(self):
        assert ai_client.crop_name("paddy", "en") == "paddy"

    def test_unknown_crop_degrades_gracefully(self):
        assert ai_client.crop_name("mustard", "bn") == "mustard"

    def test_every_calendar_crop_has_all_languages(self):
        """The four crops in data/crop_calendar.csv."""
        for crop in ("paddy", "wheat", "maize", "tomato"):
            for lang in ("hi", "kho", "bn"):
                assert ai_client.CROP_NAMES[crop].get(lang), f"{crop} missing {lang}"

    def test_context_block_uses_the_local_crop_name(self):
        block = ai_client.build_context_block(
            {"crop": "paddy", "growth_stage": "VEGETATIVE"}, "bn"
        )
        assert "ধান" in block
        assert "paddy" not in block


class TestActionsMustBeFieldTasks:
    """
    Live runs spent one of only three actions on "consult your KVK" — a
    third of the advice, given to a farmer who opened the app precisely
    because they wanted to know what to do without asking anyone.
    """

    EVENT = {"evidence": {"rain_mm_next_48h": 61.4}}

    def _advisory(self, actions):
        return {
            "headline": "बारिश",
            "body": "61.4 मिमी बारिश।",
            "actions": actions,
            "spoken_script": "बारिश आ रही है।",
        }

    def test_exact_kvk_phrase_as_action_is_rejected(self):
        adv = self._advisory(
            ["नाली साफ करें", "छिड़काव रोकें", ai_client.KVK_PHRASE["hi"]]
        )
        assert validate_advisory(adv, self.EVENT, "hi") is False

    def test_paraphrased_kvk_action_is_rejected(self):
        adv = self._advisory(["नाली साफ करें", "छिड़काव रोकें", "KVK से पूछें"])
        assert validate_advisory(adv, self.EVENT, "hi") is False

    def test_bengali_kvk_action_is_rejected(self):
        adv = self._advisory(
            ["নালা পরিষ্কার", "স্প্রে বন্ধ", ai_client.KVK_PHRASE["bn"]]
        )
        assert validate_advisory(adv, self.EVENT, "bn") is False

    def test_three_real_field_tasks_pass(self):
        adv = self._advisory(
            ["नाली साफ करें", "छिड़काव रोकें", "जमा पानी निकालें"]
        )
        assert validate_advisory(adv, self.EVENT, "hi") is True

    def test_kvk_mention_inside_body_is_fine(self):
        """The phrase belongs in body — only the action list is policed."""
        adv = self._advisory(
            ["नाली साफ करें", "छिड़काव रोकें", "जमा पानी निकालें"]
        )
        adv["body"] = f"61.4 मिमी बारिश। {ai_client.KVK_PHRASE['hi']}।"
        assert validate_advisory(adv, self.EVENT, "hi") is True

    def test_a_long_action_mentioning_kvk_is_not_flagged(self):
        """Guard against over-matching a genuine task that names the KVK."""
        adv = self._advisory(
            [
                "नाली साफ करें",
                "छिड़काव रोकें",
                "खेत का पानी निकालकर मेड़ मजबूत करें और KVK के सुझाए तरीके से ढकें",
            ]
        )
        assert validate_advisory(adv, self.EVENT, "hi") is True
