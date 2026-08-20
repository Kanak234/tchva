"""
Gemini AI Client — Section 19 of the build spec.

Two uses:
  A) Advisory generation from a RiskEvent
  B) Grounded question answering (Bolo Kisan)

Neither is allowed to decide whether a risk exists.
"""

from __future__ import annotations

import json
import logging
import os
import re

import httpx

# google-genai is optional at test time — validate_advisory and extract_numbers
# are pure functions and must be importable without the SDK.
try:
    from google import genai
    from google.genai import types
    _GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore
    _GENAI_AVAILABLE = False

logger = logging.getLogger("fasal_kavach.ai")

# ---------------------------------------------------------------------------
# Ollama and Local LLM fallback settings
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma2")
USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() == "true"


def get_ai_backend() -> str:
    """Return the active AI backend ('ollama', 'gemini', or 'template')."""
    if USE_OLLAMA:
        return "ollama"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    return "template"


async def call_ollama(system_instruction: str, prompt: str, format_json: bool) -> str:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    if format_json:
        payload["format"] = "json"
        
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"]


# ---------------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------------
_client = None  # type: ignore


def get_client():
    """Return a Gemini client, raising ImportError if SDK not installed."""
    global _client
    if not _GENAI_AVAILABLE:
        raise ImportError("google-genai not installed")
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            _client = genai.Client(api_key=api_key)
        else:
            _client = genai.Client()
    return _client


MODEL = "gemini-3.5-flash"


# ---------------------------------------------------------------------------
# Advisory generation — Section 19.1
# ---------------------------------------------------------------------------
ADVISORY_SYSTEM = """You are an agricultural extension officer writing a short warning
for a smallholder farmer who may not read well.

HARD RULES:
1. Use ONLY the facts in the CONTEXT block. Never add a number,
   date, crop name, chemical name or quantity that is not there.
2. Do not change or soften the severity. It is given to you.
3. Do not recommend any specific pesticide, fungicide or dosage.
   Say "consult your KVK or agri-dealer" instead.
4. Write in {language}. Use everyday spoken words, not textbook
   or officialese vocabulary.
5. spoken_script must sound natural read aloud: short sentences,
   no brackets, no abbreviations, no digits written as symbols.
6. Return ONLY the JSON object. No markdown, no preamble."""


ADVISORY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "actions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string"},
        },
        "spoken_script": {"type": "string"},
    },
    "required": ["headline", "body", "actions", "spoken_script"],
}

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "en": "English",
    "kho": "Khortha (written in Devanagari script)",
    "bn": "Bengali",
}


def build_context_block(event: dict) -> str:
    """Build the CONTEXT block for advisory generation."""
    lines = [
        "CONTEXT",
        f"  crop: {event.get('crop', '')}",
        f"  growth_stage: {event.get('growth_stage', '')}",
        f"  risk: {event.get('rule_id', '')}",
        f"  severity: {event.get('severity', '')}",
        f"  window: {event.get('window_start', '')} to {event.get('window_end', '')}",
    ]

    evidence = event.get("evidence", {})
    if evidence:
        lines.append("  evidence:")
        for k, v in evidence.items():
            label = k.replace("_", " ")
            lines.append(f"    {label}: {v}")

    actions = event.get("recommended_actions", [])
    if actions:
        lines.append(
            f"  recommended_actions (expand these, do not invent others): {', '.join(actions)}"
        )

    # Optional farm context
    if "area_ha" in event:
        lines.append(f"  area_ha: {event['area_ha']}")
    if "irrigation" in event:
        lines.append(f"  irrigation: {event['irrigation']}")
    if "village" in event:
        lines.append(f"  village: {event['village']}")

    return "\n".join(lines)


async def generate_advisory(
    event: dict, language: str
) -> dict | None:
    """
    Generate a structured advisory from a RiskEvent using Gemini or Ollama.

    Returns the advisory dict on success, None on failure (caller falls
    back to template).
    """
    ai_choice = get_ai_backend()
    if ai_choice == "template":
        logger.info("AI backend set to template, skipping LLM generation")
        return None

    lang_name = LANGUAGE_NAMES.get(language, "Hindi")
    system_instruction = ADVISORY_SYSTEM.format(language=lang_name)
    context_block = build_context_block(event)

    try:
        if ai_choice == "ollama":
            logger.info(f"Generating advisory using local Ollama model {OLLAMA_MODEL}")
            text = await call_ollama(system_instruction, context_block, format_json=True)
            result = json.loads(text)
            if not validate_advisory(result, event):
                logger.warning("Ollama advisory failed validation, retrying once")
                text2 = await call_ollama(
                    system_instruction,
                    context_block + "\n\nIMPORTANT: Use ONLY numbers from the context. Do NOT add any number not listed above.",
                    format_json=True
                )
                result2 = json.loads(text2)
                if validate_advisory(result2, event):
                    return result2
                logger.warning("Ollama advisory failed validation on retry, falling back to template")
                return None
            return result

        client = get_client()
        response = client.models.generate_content(
            model=MODEL,
            contents=[context_block],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=ADVISORY_SCHEMA,
                temperature=0.2,
                max_output_tokens=1024,
            ),
        )

        text = response.text
        if not text:
            logger.warning("Gemini returned empty text for advisory")
            return None

        result = json.loads(text)

        # Post-generation validation — Section 19.2
        if not validate_advisory(result, event):
            # Retry once with stricter reminder
            logger.warning("Advisory failed validation, retrying")
            response2 = client.models.generate_content(
                model=MODEL,
                contents=[
                    context_block
                    + "\n\nIMPORTANT: Use ONLY numbers from the context. "
                    "Do NOT add any number not listed above."
                ],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ADVISORY_SCHEMA,
                    temperature=0.1,
                    max_output_tokens=1024,
                ),
            )
            text2 = response2.text
            if text2:
                result2 = json.loads(text2)
                if validate_advisory(result2, event):
                    return result2

            logger.warning("Advisory failed validation on retry, falling back to template")
            return None

        return result

    except Exception:
        logger.exception(f"AI advisory generation failed using {ai_choice}")
        return None


# ---------------------------------------------------------------------------
# Post-generation validation — Section 19.2
# ---------------------------------------------------------------------------
# Banned terms: no pesticide or fungicide trade names, no dosage strings
BANNED_PATTERNS = re.compile(
    r"\b(carbendazim|mancozeb|chlorpyrifos|imidacloprid|monocrotophos|"
    r"endosulfan|malathion|thiram|metalaxyl|triazophos|cartap)\b",
    re.IGNORECASE,
)
DOSAGE_PATTERN = re.compile(r"\d+\s*(mg|ml|g|kg|litr|liter)\b", re.IGNORECASE)


def extract_numbers(text: str) -> set[float]:
    """Extract all numeric values from text."""
    nums = set()
    for match in re.findall(r"-?\d+\.?\d*", text):
        try:
            nums.add(float(match))
        except ValueError:
            pass
    return nums


def validate_advisory(result: dict, event: dict) -> bool:
    """
    Validate generated advisory against the containment rules.

    Gates:
    1. Schema — has required fields, length limits
    2. Number containment — every number in output appears in context
    3. Banned content — no pesticide names, no dosage
    """
    # Gate 1: Schema
    for field in ("headline", "body", "actions", "spoken_script"):
        if field not in result:
            return False

    if len(result.get("headline", "")) > 80:  # some slack over 60
        return False
    if len(result.get("actions", [])) != 3:
        return False

    # Gate 2: Number containment
    #
    # Every number in the output must be traceable to the event.
    #
    # This used to whitelist {0,1,2,3,4,5,6,7} as "safe", on the theory
    # that small numbers are days and dates. That was too generous: it
    # let a hallucinated "apply 5 kg per acre" through the gate, which is
    # exactly the failure this project claims to have designed out.
    #
    # Now: numbers come from the whole event (evidence, thresholds,
    # window dates, day counts), plus only {1,2,3} for the three numbered
    # actions. A model inventing a quantity gets rejected.
    context_text = json.dumps(event, default=str)
    context_nums = extract_numbers(context_text)
    context_nums.update({1, 2, 3})

    output_text = " ".join(
        [
            result.get("headline", ""),
            result.get("body", ""),
            " ".join(result.get("actions", [])),
            result.get("spoken_script", ""),
        ]
    )
    output_nums = extract_numbers(output_text)

    # Check that all output numbers exist in context
    hallucinated = output_nums - context_nums
    if hallucinated:
        logger.warning(f"Hallucinated numbers in advisory: {hallucinated}")
        return False

    # Gate 3: Banned content
    if BANNED_PATTERNS.search(output_text):
        logger.warning("Advisory contains banned pesticide name")
        return False
    if DOSAGE_PATTERN.search(output_text):
        logger.warning("Advisory contains dosage string")
        return False

    return True


# ---------------------------------------------------------------------------
# Grounded Q&A — Section 19.4 (Bolo Kisan)
# ---------------------------------------------------------------------------
ASK_SYSTEM = """Answer the farmer's question using ONLY the CONTEXT below.
If the answer is not in the context, reply exactly with the
phrase for "I do not have that information for your farm.
Please ask your local KVK." in {language}, and nothing else.
Never give chemical names or dosages. Keep the answer under
50 words. Return JSON: {{"answer_text": "...", "spoken_script": "...", "grounded": true/false}}."""

ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "answer_text": {"type": "string"},
        "spoken_script": {"type": "string"},
        "grounded": {"type": "boolean"},
    },
    "required": ["answer_text", "spoken_script", "grounded"],
}


async def ask_question(
    question: str,
    language: str,
    context: dict,
) -> dict:
    """
    Answer a farmer's question grounded in their farm data.

    Returns dict with answer_text, spoken_script, grounded, used_context.
    """
    ai_choice = get_ai_backend()
    if ai_choice == "template":
        logger.info("AI backend set to template, returning ungrounded response")
        return _ungrounded_response(language)

    lang_name = LANGUAGE_NAMES.get(language, "Hindi")
    system_instruction = ASK_SYSTEM.format(language=lang_name)

    context_block = "CONTEXT\n"
    used_context = []

    # Farm profile
    if "farm" in context:
        farm = context["farm"]
        context_block += f"  Farm: {farm.get('crop', '')} in {farm.get('village', '')}\n"
        context_block += f"  Sowing: {farm.get('sowing_date', '')}, Area: {farm.get('area_ha', '')} ha\n"
        context_block += f"  Irrigation: {farm.get('irrigation', '')}\n"
        context_block += f"  Growth stage: {farm.get('growth_stage', '')}\n"
        used_context.append("farm_profile")

    # 7-day forecast
    if "forecast" in context:
        context_block += "  7-day forecast:\n"
        for day in context["forecast"]:
            context_block += (
                f"    {day.get('date', '')}: rain {day.get('rain_mm', 0)} mm, "
                f"temp {day.get('t_min_c', 0)}-{day.get('t_max_c', 0)}°C\n"
            )
            used_context.append(f"forecast_{day.get('date', '')}")

    # Active advisories
    if "advisories" in context:
        context_block += "  Active advisories:\n"
        for adv in context["advisories"]:
            context_block += f"    - {adv.get('headline', '')} ({adv.get('severity', '')})\n"
            used_context.append(f"advisory_{adv.get('event_id', '')}")

    try:
        if ai_choice == "ollama":
            logger.info(f"Answering question using local Ollama model {OLLAMA_MODEL}")
            prompt = f"Question: {question}\n\n{context_block}"
            text = await call_ollama(system_instruction, prompt, format_json=True)
        else:
            client = get_client()
            response = client.models.generate_content(
                model=MODEL,
                contents=[f"Question: {question}\n\n{context_block}"],
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=ASK_SCHEMA,
                    temperature=0.3,
                    max_output_tokens=512,
                ),
            )
            text = response.text
        if not text:
            return _ungrounded_response(language)

        result = json.loads(text)

        # Verify grounded flag — Section 19.4
        if result.get("grounded", False):
            context_nums = extract_numbers(context_block)
            context_nums.update({0, 1, 2, 3, 4, 5, 6, 7})
            answer_nums = extract_numbers(result.get("answer_text", ""))
            if answer_nums - context_nums:
                result["grounded"] = False

        result["used_context"] = used_context
        return result

    except Exception:
        logger.exception(f"AI Q&A failed using {ai_choice}")
        return _ungrounded_response(language)


def _ungrounded_response(language: str) -> dict:
    """Fallback when AI is unavailable."""
    messages = {
        "hi": "मेरे पास आपके खेत के लिए यह जानकारी नहीं है। कृपया अपने नजदीकी KVK से पूछें।",
        "en": "I do not have that information for your farm. Please ask your local KVK.",
        "kho": "हमरा लगे ई जानकारी नइखे। अपने KVK से पूछो।",
        "bn": "আমার কাছে আপনার জমির জন্য এই তথ্য নেই। আপনার স্থানীয় KVK-তে জিজ্ঞাসা করুন।",
    }
    msg = messages.get(language, messages["en"])
    return {
        "answer_text": msg,
        "spoken_script": msg,
        "grounded": False,
        "used_context": [],
        "confidence_note": "AI unavailable or question outside context",
    }
