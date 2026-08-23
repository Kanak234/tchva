"""
AI client — advisory generation and grounded Q&A.

Two uses:
  A) Advisory generation from a RiskEvent
  B) Grounded question answering (Bolo Kisan)

Neither is allowed to decide whether a risk exists. The rules engine
decides that; the model only puts it into words a farmer can act on.

BACKEND LADDER
--------------
Backends are tried in order and the first one that returns output
passing validation wins. A backend that errors, times out, or produces
an invalid advisory does not sink the request — the next one runs, and
if all of them fail the caller falls back to the deterministic template.
That ordering is the whole point: a farmer should get a usable warning
even when every model provider is down.

Default order: groq -> gemini -> ollama -> template
Override with AI_BACKENDS="gemini,template" etc.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import unicodedata

import httpx

# google-genai is optional at test time — validate_advisory and
# extract_numbers are pure functions and must import without the SDK.
try:
    from google import genai
    from google.genai import types

    _GENAI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the SDK
    genai = None  # type: ignore
    types = None  # type: ignore
    _GENAI_AVAILABLE = False

logger = logging.getLogger("fasal_kavach.ai")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma2")
USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() == "true"

GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
# Groq announced the deprecation of llama-3.3-70b-versatile on 17 Jun 2026
# and points users at gpt-oss-120b. Defaulting to a deprecated id is how you
# wake up to 404s on demo day, so the default is the recommended migration
# target. Override with GROQ_MODEL if you want something else.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Gemini 3.x replaced the integer thinking_budget with a thinking_level
# enum (minimal | low | medium | high) and defaults to medium. Advisory
# generation is a formatting job, not a reasoning job: left on medium the
# thinking tokens eat max_output_tokens and generateContent comes back with
# finish_reason=MAX_TOKENS and empty text. That is the "structured output
# fails every time" symptom.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "minimal")

HTTP_TIMEOUT = float(os.getenv("AI_HTTP_TIMEOUT", "45"))

# Kept for backward compatibility. get_backend_ladder() is what the
# generation paths actually use.
MODEL = GEMINI_MODEL


def get_ai_backend() -> str:
    """Return the single highest-priority backend name."""
    ladder = get_backend_ladder()
    return ladder[0] if ladder else "template"


def get_backend_ladder() -> list[str]:
    """
    Resolve the ordered list of backends to try.

    An explicit AI_BACKENDS setting always wins, so a deployment can pin
    the order without touching code.
    """
    explicit = os.getenv("AI_BACKENDS", "").strip()
    if explicit:
        names = [n.strip().lower() for n in explicit.split(",") if n.strip()]
        return names or ["template"]

    ladder: list[str] = []
    # An explicit USE_OLLAMA is a deliberate "run it locally, spend nothing"
    # choice, so it goes to the front rather than acting as a last resort.
    if USE_OLLAMA:
        ladder.append("ollama")
    if os.getenv("GROQ_API_KEY"):
        ladder.append("groq")
    if os.getenv("GEMINI_API_KEY"):
        ladder.append("gemini")
    ladder.append("template")
    return ladder


def model_id_for(backend: str) -> str:
    """
    The concrete model id a backend would use.

    Stored on each advisory so provenance is real. An advisory that says
    it came from Gemini when Ollama wrote it is a lie in the audit trail,
    and this project's whole pitch is that its advice is traceable.
    """
    return {
        "groq": GROQ_MODEL,
        "gemini": GEMINI_MODEL,
        "ollama": OLLAMA_MODEL,
    }.get(backend, backend)


# ---------------------------------------------------------------------------
# Backend calls — each returns raw text or raises
# ---------------------------------------------------------------------------
async def call_ollama(system_instruction: str, prompt: str, format_json: bool) -> str:
    url = f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat"
    payload: dict = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    if format_json:
        payload["format"] = "json"

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()["message"]["content"]


async def call_groq(system_instruction: str, prompt: str, format_json: bool) -> str:
    """
    Call Groq's OpenAI-compatible chat completions endpoint.

    Uses httpx directly rather than the groq SDK: this is one POST, and
    the SDK would be another dependency to pin and another sync client to
    wrap in a thread.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set")

    payload: dict = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    if format_json:
        payload["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
        response = await client.post(
            f"{GROQ_BASE_URL.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]


_client = None  # type: ignore


def get_client():
    """Return a Gemini client, raising ImportError if the SDK is absent."""
    global _client
    if not _GENAI_AVAILABLE:
        raise ImportError("google-genai not installed")
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        _client = genai.Client(api_key=api_key) if api_key else genai.Client()
    return _client


def _gemini_config(system_instruction: str, schema: dict):
    """
    Build a GenerateContentConfig for a Gemini 3.x model.

    Two things differ from the 2.5-era config this used to send:

      - thinking_level replaces thinking_budget. Passing the integer form
        to a 3.x model does not disable thinking, so the model burned its
        output budget on reasoning and returned nothing.
      - temperature / top_p / top_k are deprecated on 3.x and are no
        longer sent at all.

    ThinkingConfig is probed with hasattr because an older installed SDK
    will not have the thinking_level field, and a hard reference would
    turn a config mismatch into an import-time crash.
    """
    kwargs: dict = {
        "system_instruction": system_instruction,
        "response_mime_type": "application/json",
        "response_schema": schema,
        "max_output_tokens": 4096,
    }

    if types is not None and hasattr(types, "ThinkingConfig"):
        try:
            kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=GEMINI_THINKING_LEVEL
            )
        except (TypeError, ValueError):
            logger.debug(
                "Installed google-genai does not accept thinking_level; "
                "leaving thinking at the model default"
            )

    return types.GenerateContentConfig(**kwargs)


async def call_gemini(system_instruction: str, prompt: str, schema: dict) -> str:
    """
    Call Gemini and return the raw JSON text.

    generate_content is synchronous. Calling it straight from an async
    route blocks the event loop for the whole round trip and stalls every
    other request on the worker, so it runs in a thread — the same reason
    db.py wraps firebase-admin.
    """
    client = get_client()
    config = _gemini_config(system_instruction, schema)

    response = await asyncio.to_thread(
        client.models.generate_content,
        model=GEMINI_MODEL,
        contents=[prompt],
        config=config,
    )

    text = response.text
    if not text:
        finish = (
            response.candidates[0].finish_reason
            if getattr(response, "candidates", None)
            else "NO_CANDIDATES"
        )
        raise RuntimeError(f"Gemini returned no text (finish_reason={finish})")
    return text


async def _call_backend(
    backend: str, system_instruction: str, prompt: str, schema: dict
) -> str:
    # Only Gemini accepts a response_schema. The others are told the shape
    # in words instead — see _schema_hint().
    if backend == "groq":
        return await call_groq(
            system_instruction + _schema_hint(schema), prompt, format_json=True
        )
    if backend == "ollama":
        return await call_ollama(
            system_instruction + _schema_hint(schema), prompt, format_json=True
        )
    if backend == "gemini":
        return await call_gemini(system_instruction, prompt, schema)
    raise ValueError(f"Unknown backend: {backend}")


def _schema_hint(schema: dict) -> str:
    """
    Describe a JSON schema in the prompt itself.

    Gemini takes response_schema and is told the exact shape. Groq and
    Ollama get response_format=json_object, which only guarantees *valid*
    JSON — not JSON with our keys. Without this they returned well-formed
    objects with invented field names and every advisory was rejected for
    a missing headline.

    Derived from the schema rather than written out by hand, so the prompt
    cannot drift away from what validate_advisory() actually requires.
    """
    props = schema.get("properties", {})
    required = schema.get("required", list(props))
    lines = []
    for key in required:
        kind = props.get(key, {}).get("type", "string")
        if kind == "array":
            item = props[key].get("items", {}).get("type", "string")
            lines.append(f'  "{key}": [{item}, {item}, {item}]')
        elif kind == "boolean":
            lines.append(f'  "{key}": true or false')
        else:
            lines.append(f'  "{key}": {kind}')
    body = ",\n".join(lines)
    return (
        "\n\nReturn a JSON object with exactly these keys and nothing else:\n"
        "{\n" + body + "\n}"
    )


def _parse_json(text: str) -> dict:
    """
    Parse a model's JSON reply, tolerating fenced or padded output.

    Models that do not honour a JSON response format still wrap output in
    ```json fences often enough that failing the whole advisory over it
    would be wasteful.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


# ---------------------------------------------------------------------------
# Advisory generation
# ---------------------------------------------------------------------------
# Phrases the model is instructed to reproduce.
#
# These have to be supplied in the target language. When rule 3 said
# 'Say "consult your KVK or agri-dealer"', the model did exactly that —
# in English, inside otherwise fluent Hindi. Any literal string the
# prompt asks the model to output must be localised, for the same reason
# STAGE_NAMES exists.
KVK_PHRASE = {
    "hi": "अपने KVK या कृषि दुकानदार से सलाह लें",
    "en": "consult your KVK or agri-dealer",
    "kho": "अपन KVK या खेती के दुकानदार सें सलाह लेवा",
    "bn": "আপনার KVK বা কৃষি দোকানদারের পরামর্শ নিন",
}

NO_INFO_PHRASE = {
    "hi": "मेरे पास आपके खेत के लिए यह जानकारी नहीं है। कृपया अपने नजदीकी KVK से पूछें।",
    "en": "I do not have that information for your farm. Please ask your local KVK.",
    "kho": "हमरा लगे ई जानकारी नइखे। अपने KVK से पूछो।",
    "bn": "আমার কাছে আপনার জমির জন্য এই তথ্য নেই। আপনার স্থানীয় KVK-তে জিজ্ঞাসা করুন।",
}


ADVISORY_SYSTEM = """You are an agricultural extension officer writing a short warning
for a smallholder farmer who may not read well.

HARD RULES:
1. Use ONLY the facts in the CONTEXT block. Never add a number,
   date, crop name, chemical name or quantity that is not there.
2. Do not change or soften the severity. It is given to you.
3. Do not recommend any specific pesticide, fungicide or dosage.
   Write exactly this instead, word for word: "{kvk_phrase}"
4. Write in {language}. Use everyday spoken words, not textbook
   or officialese vocabulary.
5. spoken_script must sound natural read aloud: short sentences,
   no brackets, no abbreviations, no digits written as symbols.
6. actions must contain EXACTLY three items. Each one is something the
   farmer does with their hands, in their field, today or tomorrow —
   walk, clear, dig, cover, delay, move, drain. Never put "{kvk_phrase}"
   or any other advice-seeking step in this list: it belongs in body, and
   spending one of only three actions on it wastes a third of what the
   farmer is told to do.
7. Every word must be in {language}. Do not leave English words in
   the text, not even technical or stage names — the CONTEXT already
   gives them in the right language, so use those exactly.
8. Return ONLY the JSON object. No markdown, no preamble."""

ADVISORY_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "actions": {"type": "array", "items": {"type": "string"}},
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

RETRY_NOTE = (
    "\n\nIMPORTANT: Use ONLY numbers from the context. "
    "Do NOT add any number not listed above. "
    "Return exactly three actions."
)


CROP_NAMES: dict[str, dict[str, str]] = {
    "paddy": {"hi": "धान", "kho": "धान", "bn": "ধান"},
    "wheat": {"hi": "गेहूँ", "kho": "गेहूँ", "bn": "গম"},
    "maize": {"hi": "मक्का", "kho": "मकई", "bn": "ভুট্টা"},
    "tomato": {"hi": "टमाटर", "kho": "टमाटर", "bn": "টমেটো"},
}


def crop_name(crop: str, language: str) -> str:
    """Local name for a crop, falling back to the English slug."""
    if not crop:
        return ""
    key = crop.strip().lower()
    if language == "en":
        return key
    return CROP_NAMES.get(key, {}).get(language, key)


# Growth-stage names as they should be spoken to a farmer.
#
# The stage arrives from crop_calendar.csv as an English slug
# ("vegetative", "grain_fill"). Handed to the model raw, it came straight
# back out in the middle of otherwise fluent Hindi — "धान की बाली अभी
# vegetative stage में है" — because the model had no word to use instead.
# Giving it the local term is more reliable than instructing it to
# translate, and it keeps the vocabulary consistent across every advisory.
STAGE_NAMES: dict[str, dict[str, str]] = {
    "nursery": {"hi": "नर्सरी", "kho": "नर्सरी", "bn": "নার্সারি"},
    "transplant_establish": {
        "hi": "रोपाई के बाद जमाव", "kho": "रोपनी के बाद जमाव",
        "bn": "রোপণের পর প্রতিষ্ঠা",
    },
    "germination": {"hi": "अंकुरण", "kho": "अंकुरन", "bn": "অঙ্কুরোদগম"},
    "seedling": {"hi": "पौध", "kho": "पौधा", "bn": "চারা"},
    "vegetative": {"hi": "बढ़वार", "kho": "बढ़वार", "bn": "বৃদ্ধি"},
    "tillering": {"hi": "कल्ले फूटना", "kho": "कल्ला फूटब", "bn": "কুশি ছাড়া"},
    "jointing": {"hi": "गाँठ बनना", "kho": "गाँठ बनब", "bn": "গাঁট বাঁধা"},
    "tasseling": {"hi": "झालर निकलना", "kho": "झालर निकलब", "bn": "মঞ্জরি"},
    "flowering": {"hi": "फूल आना", "kho": "फूल आयब", "bn": "ফুল আসা"},
    "fruiting": {"hi": "फल लगना", "kho": "फल लागब", "bn": "ফল ধরা"},
    "grain_fill": {"hi": "दाना भरना", "kho": "दाना भरब", "bn": "দানা ভরা"},
    "maturity": {"hi": "पकाई", "kho": "पकाई", "bn": "পরিপক্বতা"},
    "harvest": {"hi": "कटाई", "kho": "कटनी", "bn": "কাটা"},
}


def stage_name(stage: str, language: str) -> str:
    """Local name for a growth stage, falling back to the English slug."""
    if not stage:
        return ""
    key = stage.strip().lower().replace(" ", "_")
    readable = key.replace("_", " ")
    if language == "en":
        return readable
    return STAGE_NAMES.get(key, {}).get(language, readable)


def build_context_block(event: dict, language: str = "hi") -> str:
    """Build the CONTEXT block for advisory generation."""
    stage = stage_name(event.get("growth_stage", ""), language)
    lines = [
        "CONTEXT",
        f"  crop: {crop_name(event.get('crop', ''), language)}",
        f"  growth_stage: {stage}",
        f"  risk: {event.get('rule_id', '')}",
        f"  severity: {event.get('severity', '')}",
        f"  window: {event.get('window_start', '')} to {event.get('window_end', '')}",
    ]

    evidence = event.get("evidence", {})
    if evidence:
        lines.append("  evidence:")
        for k, v in evidence.items():
            lines.append(f"    {k.replace('_', ' ')}: {v}")

    actions = event.get("recommended_actions", [])
    if actions:
        lines.append(
            "  recommended_actions (expand these, do not invent others): "
            + ", ".join(actions)
        )

    for key in ("area_ha", "irrigation", "village"):
        if key in event:
            lines.append(f"  {key}: {event[key]}")

    return "\n".join(lines)


async def generate_advisory(event: dict, language: str) -> dict | None:
    """
    Generate a structured advisory from a RiskEvent.

    Walks the backend ladder. Each backend gets one retry with a stricter
    reminder before the ladder moves on. Returns None when nothing passes,
    and the caller renders the deterministic template instead.
    """
    lang_name = LANGUAGE_NAMES.get(language, "Hindi")
    system_instruction = ADVISORY_SYSTEM.format(
        language=lang_name, kvk_phrase=KVK_PHRASE.get(language, KVK_PHRASE["en"])
    )
    context_block = build_context_block(event, language)

    for backend in get_backend_ladder():
        if backend == "template":
            logger.info("Advisory ladder reached template fallback")
            return None

        for attempt, prompt in enumerate((context_block, context_block + RETRY_NOTE)):
            try:
                text = await _call_backend(
                    backend, system_instruction, prompt, ADVISORY_SCHEMA
                )
                result = _parse_json(text)
            except Exception as exc:
                logger.warning(
                    "Advisory generation via %s failed (attempt %d): %s",
                    backend,
                    attempt + 1,
                    exc,
                )
                continue

            if validate_advisory(result, event, language):
                logger.info("Advisory generated by %s", backend)
                result["generated_by"] = backend
                return result

            logger.warning(
                "Advisory from %s failed validation (attempt %d)", backend, attempt + 1
            )

        logger.warning("Backend %s exhausted, trying next in ladder", backend)

    return None


# ---------------------------------------------------------------------------
# Post-generation validation
# ---------------------------------------------------------------------------
BANNED_PATTERNS = re.compile(
    r"\b(carbendazim|mancozeb|chlorpyrifos|imidacloprid|monocrotophos|"
    r"endosulfan|malathion|thiram|metalaxyl|triazophos|cartap)\b",
    re.IGNORECASE,
)
DOSAGE_PATTERN = re.compile(r"\d+\s*(mg|ml|g|kg|litr|liter)\b", re.IGNORECASE)


def _to_ascii_digits(text: str) -> str:
    """
    Fold Devanagari, Bengali and other Unicode digits to ASCII.

    Not a bug fix — CPython's float() already parses "६१.४" correctly, so
    the gate was never blind to Hindi numerals. This makes that behaviour
    explicit rather than inherited: the containment gate is the safety
    property this whole project rests on, and it should not depend on a
    CPython parsing convenience that no test pins down.
    """
    return "".join(
        str(unicodedata.digit(ch)) if ch.isdigit() and not ch.isascii() else ch
        for ch in text
    )


# A hyphen only means "minus" when it does not follow a digit.
#
# The old pattern read "2026-08-22" as 2026, -8, -22. So the context block
# recorded the window as negative numbers while the model, writing the same
# dates in prose, produced positive ones — and the gate rejected a correct
# advisory for "hallucinating" the very dates it had been handed. Every
# advisory that mentioned its own window died this way, which sends the
# whole ladder to the template even when both providers answered well.
#
# Found by making a real API call. The mocked tests all used clean numbers
# and never contained a date, so none of them could see it.
_NUMBER_RE = re.compile(r"(?<![\d.])-?\d+(?:\.\d+)?")


def extract_numbers(text: str) -> set[float]:
    """Extract all numeric values from text, in any digit script."""
    nums: set[float] = set()
    for match in _NUMBER_RE.findall(_to_ascii_digits(text)):
        try:
            nums.add(float(match))
        except ValueError:
            pass
    return nums


def _is_advice_seeking(text: str, language: str) -> bool:
    """
    True when an action is really "go and ask someone".

    Matched loosely: models paraphrase the phrase rather than copying it,
    so a substring test alone would miss most cases.
    """
    lowered = text.strip().lower().rstrip(".।!")
    phrase = KVK_PHRASE.get(language, "").lower().rstrip(".।!")
    if phrase and (lowered == phrase or phrase in lowered):
        return True
    return bool(re.search(r"\bkvk\b", lowered)) and len(lowered) < 60


def validate_advisory(result: dict, event: dict, language: str = "hi") -> bool:
    """
    Validate a generated advisory against the containment rules.

    Gates:
      1. Schema — required fields present, length limits, exactly 3 actions
      2. Number containment — every number in the output traces to the event
      3. Banned content — no pesticide trade names, no dosages
    """
    for field in ("headline", "body", "actions", "spoken_script"):
        if field not in result:
            logger.warning("Advisory rejected: missing field %r", field)
            return False

    headline = result.get("headline", "")
    if len(headline) > 80:
        logger.warning(
            "Advisory rejected: headline is %d chars, limit is 80", len(headline)
        )
        return False

    actions = result.get("actions", [])
    if len(actions) != 3:
        logger.warning("Advisory rejected: %d actions, expected exactly 3", len(actions))
        return False

    # An action the farmer cannot perform in the field is not an action.
    for action in actions:
        if _is_advice_seeking(action, language):
            logger.warning(
                "Advisory rejected: action %r is advice-seeking, not a field task",
                action,
            )
            return False

    # Gate 2: number containment.
    #
    # This used to whitelist {0..7} as "safe", on the theory that small
    # numbers are days and dates. Too generous: it let a hallucinated
    # "apply 5 kg per acre" through the gate this project exists to close.
    # Now only {1,2,3} are free, for the three numbered actions.
    context_nums = extract_numbers(json.dumps(event, default=str))
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

    hallucinated = output_nums - context_nums
    if hallucinated:
        logger.warning(
            "Advisory rejected: numbers not in context: %s", sorted(hallucinated)
        )
        return False

    banned = BANNED_PATTERNS.search(output_text)
    if banned:
        logger.warning("Advisory rejected: names pesticide %r", banned.group(0))
        return False
    dosage = DOSAGE_PATTERN.search(_to_ascii_digits(output_text))
    if dosage:
        logger.warning("Advisory rejected: contains dosage %r", dosage.group(0))
        return False

    return True


# ---------------------------------------------------------------------------
# Grounded Q&A (Bolo Kisan)
# ---------------------------------------------------------------------------
def _language_rule(lang_name: str, language: str) -> str:
    """
    The write-in-this-language instruction.

    Needs a separate branch for English, because the shared wording told
    an English request to "write every word in English; leave no English
    in the output" — an instruction that contradicts itself and gives the
    model nothing usable.
    """
    if language == "en":
        return "Write in plain English a farmer can read easily."
    return (
        f"Write every word in {lang_name}. Leave no English in the "
        f"output — the CONTEXT already gives crop and stage names in "
        f"{lang_name}, so use those exactly."
    )


ASK_SYSTEM = """Answer the farmer's question using ONLY the CONTEXT below.

The CONTEXT holds their farm details and their weather forecast. If the
answer can be worked out from those numbers, answer it directly and set
grounded to true.

Only if the CONTEXT genuinely does not contain the answer, reply with
exactly this text, word for word, and set grounded to false:
"{no_info_phrase}"

Never name a chemical or give a dose. If the farmer asks which product or
how much to apply, answer the part you can from the CONTEXT, then add
this sentence at the end — do not send it on its own:
"{kvk_phrase}"

{language_rule}
Keep the answer under 50 words.
Return JSON: {{"answer_text": "...", "spoken_script": "...", "grounded": true/false}}."""


ASK_SCHEMA = {
    "type": "object",
    "properties": {
        "answer_text": {"type": "string"},
        "spoken_script": {"type": "string"},
        "grounded": {"type": "boolean"},
    },
    "required": ["answer_text", "spoken_script", "grounded"],
}


def build_ask_context(
    context: dict, language: str = "hi"
) -> tuple[str, list[str]]:
    """Render the Q&A context block and the list of what went into it."""
    block = "CONTEXT\n"
    used: list[str] = []

    if "farm" in context:
        farm = context["farm"]
        block += (
            f"  Farm: {crop_name(farm.get('crop', ''), language)} "
            f"in {farm.get('village', '')}\n"
        )
        block += (
            f"  Sowing: {farm.get('sowing_date', '')}, "
            f"Area: {farm.get('area_ha', '')} ha\n"
        )
        block += f"  Irrigation: {farm.get('irrigation', '')}\n"
        block += (
            f"  Growth stage: {stage_name(farm.get('growth_stage', ''), language)}\n"
        )
        used.append("farm_profile")

    if "forecast" in context:
        block += "  7-day forecast:\n"
        for day in context["forecast"]:
            block += (
                f"    {day.get('date', '')}: rain {day.get('rain_mm', 0)} mm, "
                f"temp {day.get('t_min_c', 0)}-{day.get('t_max_c', 0)}°C\n"
            )
            used.append(f"forecast_{day.get('date', '')}")

    if "advisories" in context:
        block += "  Active advisories:\n"
        for adv in context["advisories"]:
            block += (
                f"    - {adv.get('headline', '')} ({adv.get('severity', '')})\n"
            )
            used.append(f"advisory_{adv.get('event_id', '')}")

    return block, used


async def ask_question(question: str, language: str, context: dict) -> dict:
    """
    Answer a farmer's question grounded in their own farm data.

    Returns answer_text, spoken_script, grounded and used_context. On
    total failure it returns the honest "I do not know" rather than a
    guess — an extension officer who invents an answer is worse than one
    who says go ask the KVK.
    """
    lang_name = LANGUAGE_NAMES.get(language, "Hindi")
    system_instruction = ASK_SYSTEM.format(
        language_rule=_language_rule(lang_name, language),
        kvk_phrase=KVK_PHRASE.get(language, KVK_PHRASE["en"]),
        no_info_phrase=NO_INFO_PHRASE.get(language, NO_INFO_PHRASE["en"]),
    )
    context_block, used_context = build_ask_context(context, language)
    prompt = f"Question: {question}\n\n{context_block}"

    for backend in get_backend_ladder():
        if backend == "template":
            logger.info("Q&A ladder reached template fallback")
            return _ungrounded_response(language)

        try:
            text = await _call_backend(
                backend, system_instruction, prompt, ASK_SCHEMA
            )
            result = _parse_json(text)
        except Exception as exc:
            logger.warning("Q&A via %s failed: %s", backend, exc)
            continue

        if "answer_text" not in result:
            logger.warning("Q&A from %s missing answer_text", backend)
            continue

        # Re-check the model's own grounded claim against the context.
        # A model marking its answer grounded is not evidence that it is.
        if result.get("grounded", False):
            context_nums = extract_numbers(context_block)
            context_nums.update({0, 1, 2, 3})
            answer_nums = extract_numbers(result.get("answer_text", ""))
            if answer_nums - context_nums:
                logger.warning("Q&A answer cited numbers absent from context")
                result["grounded"] = False

        result.setdefault("spoken_script", result["answer_text"])
        result["used_context"] = used_context
        return result

    return _ungrounded_response(language)


def _ungrounded_response(language: str) -> dict:
    """Honest fallback when no backend can answer from the context."""
    msg = NO_INFO_PHRASE.get(language, NO_INFO_PHRASE["en"])
    return {
        "answer_text": msg,
        "spoken_script": msg,
        "grounded": False,
        "used_context": [],
        "confidence_note": "AI unavailable or question outside context",
    }
