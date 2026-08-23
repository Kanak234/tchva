#!/usr/bin/env python3
"""
Pre-demo live check.

Runs a real advisory and a real Q&A through the backend ladder in every
supported language, then reports what a farmer would actually see.

This exists because the test suite mocks every AI call. Mocked tests are
the right default — they are fast and they do not cost money — but four
separate defects in this project got through them and were only found by
calling the real API: a number gate that read dates as negative numbers,
a Groq prompt that never named the JSON fields, English growth-stage
slugs, and English instruction text copied verbatim into Hindi output.

All four were the same shape: something that looks fine in a unit test
and is obviously wrong the moment a person reads the output.

Run this before any demo:

    set -a && source .env && set +a
    python scripts/live_check.py

It costs a handful of API calls. Nothing is written to the database.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "api"))

from ai.client import (  # noqa: E402
    KVK_PHRASE,
    LANGUAGE_NAMES,
    NO_INFO_PHRASE,
    ask_question,
    generate_advisory,
    get_backend_ladder,
)

# Organisation names are written the same way in every language, so they
# are not evidence of an untranslated string.
ALLOWED_LATIN = {"KVK", "ICAR", "IMD", "MM", "DAS"}

EVENT = {
    "crop": "paddy",
    "growth_stage": "VEGETATIVE",
    "rule_id": "HEAVY_RAIN_PRE_SPRAY",
    "severity": "MODERATE",
    "window_start": "2026-08-22",
    "window_end": "2026-08-24",
    "evidence": {"rain_mm_next_48h": 61.4, "threshold_mm": 40.0},
    "recommended_actions": ["DELAY_SPRAY", "CHECK_DRAINAGE"],
}

ASK_CONTEXT = {
    "farm": {
        "crop": "paddy",
        "village": "Barhi",
        "sowing_date": "2026-07-01",
        "area_ha": 1.0,
        "irrigation": "rainfed",
        "growth_stage": "VEGETATIVE",
    },
    "forecast": [
        {"date": "2026-08-22", "rain_mm": 61.4, "t_min_c": 24.5, "t_max_c": 30.0}
    ],
}

QUESTIONS = {
    "hi": "क्या मैं आज छिड़काव कर सकता हूँ?",
    "en": "Can I spray today?",
    "kho": "का हम आज छिड़काव कर सकत ही?",
    "bn": "আমি কি আজ স্প্রে করতে পারি?",
}


def latin_words(text: str) -> list[str]:
    """Latin-script words that are not recognised organisation names."""
    return [
        w for w in re.findall(r"[A-Za-z]{3,}", text) if w.upper() not in ALLOWED_LATIN
    ]


def check_language(lang: str, texts: list[str]) -> list[str]:
    if lang == "en":
        return []
    return latin_words(" ".join(texts))


async def main() -> int:
    if not (os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY")):
        print("No GROQ_API_KEY or GEMINI_API_KEY in the environment.")
        print("Run:  set -a && source .env && set +a")
        return 2

    print(f"ladder: {get_backend_ladder()}\n")
    problems: list[str] = []

    for lang in LANGUAGE_NAMES:
        print("=" * 64)
        print(f"{lang.upper()}  ({LANGUAGE_NAMES[lang]})")
        print("=" * 64)

        # --- advisory
        try:
            adv = await generate_advisory(EVENT, lang)
        except Exception as exc:
            print(f"  ADVISORY: raised {exc!r}")
            problems.append(f"{lang}: advisory raised {type(exc).__name__}")
            adv = None

        if adv is None:
            print("  ADVISORY: fell through to template")
            problems.append(f"{lang}: no backend produced a valid advisory")
        else:
            print(f"  backend : {adv['generated_by']}")
            print(f"  headline: {adv['headline']}")
            print(f"  body    : {adv['body']}")
            for action in adv["actions"]:
                print(f"    - {action}")
            print(f"  spoken  : {adv['spoken_script']}")

            stray = check_language(
                lang,
                [
                    adv["headline"],
                    adv["body"],
                    " ".join(adv["actions"]),
                    adv["spoken_script"],
                ],
            )
            if stray:
                print(f"  >> ENGLISH LEFT IN: {sorted(set(stray))}")
                problems.append(f"{lang}: advisory contains {sorted(set(stray))}")
            if len(adv["actions"]) != 3:
                problems.append(f"{lang}: {len(adv['actions'])} actions, expected 3")
            kvk = KVK_PHRASE.get(lang, "").strip().rstrip(".।!")
            for action in adv["actions"]:
                if kvk and kvk in action.strip().rstrip(".।!"):
                    print(f"  >> ACTION IS ADVICE-SEEKING: {action}")
                    problems.append(
                        f"{lang}: an action is 'ask the KVK', not a field task"
                    )

        # --- grounded Q&A
        try:
            ans = await ask_question(QUESTIONS[lang], lang, ASK_CONTEXT)
        except Exception as exc:
            print(f"  ASK: raised {exc!r}")
            problems.append(f"{lang}: ask raised {type(exc).__name__}")
            ans = None

        if ans:
            print(f"  ask     : [grounded={ans['grounded']}] {ans['answer_text']}")
            stray = check_language(lang, [ans["answer_text"]])
            if stray:
                print(f"  >> ENGLISH LEFT IN: {sorted(set(stray))}")
                problems.append(f"{lang}: answer contains {sorted(set(stray))}")

            # An answer that is nothing but boilerplate is not an answer.
            # The forecast is in the context, so "ask your KVK" to a
            # spray question means the model dodged it — and the earlier
            # version of this script called that a pass, because it only
            # looked for stray English.
            body = ans["answer_text"].strip().rstrip(".।!")
            for label, table in (("KVK phrase", KVK_PHRASE), ("no-info", NO_INFO_PHRASE)):
                boilerplate = table.get(lang, "").strip().rstrip(".।!")
                if boilerplate and body == boilerplate:
                    print(f"  >> ANSWER IS ONLY THE {label.upper()} — question dodged")
                    problems.append(
                        f"{lang}: answer is only the {label}, not an answer"
                    )
            if ans["grounded"] and len(body) < 20:
                problems.append(f"{lang}: grounded answer is suspiciously short")
        print()

    print("=" * 64)
    if problems:
        print(f"{len(problems)} problem(s):\n")
        for p in problems:
            print(f"  - {p}")
        print("\nNot demo-ready.")
        return 1

    print("All four languages produced grounded output with no stray English.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
