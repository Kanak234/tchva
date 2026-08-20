#!/usr/bin/env python3
"""
check_locale_keys.py — fail the build when a translation is missing.

WHY THIS REPLACED THE OLD CI JOB
--------------------------------
The old job ran:

    node -e "const en = require('./web/src/lib/i18n.ts') || {}; ..."

Node cannot require() a TypeScript file. It threw, and `|| {}` does not
catch a throw — it only handles a falsy return. So the job failed on
every single push, and it never checked a key. A red tick nobody trusts
is worse than no tick.

WHAT THIS DOES
--------------
Parses the four language blocks out of i18n.ts and compares each one's
key set against English. Any key present in `en` and absent elsewhere
fails the build with the exact list.

Why parse instead of importing: importing means a TypeScript toolchain
in CI just to read a dictionary. A 40-line parser is cheaper and has no
dependency to break.

Run locally:  python3 scripts/check_locale_keys.py
"""

import re
import sys
from pathlib import Path

I18N = Path(__file__).resolve().parents[1] / "web" / "src" / "lib" / "i18n.ts"

BLOCK_START = re.compile(r"^  (\w+): \{$")
KEY_LINE = re.compile(r"^    '([^']+)':")
BLOCK_END = re.compile(r"^  \},?$")

REFERENCE = "en"


def parse(path: Path) -> dict[str, set[str]]:
    """Pull {lang: {keys}} out of the translations object."""
    if not path.exists():
        print(f"FAIL: {path} not found", file=sys.stderr)
        sys.exit(1)

    locales: dict[str, set[str]] = {}
    current: str | None = None

    for line in path.read_text(encoding="utf-8").splitlines():
        start = BLOCK_START.match(line)
        if start:
            current = start.group(1)
            locales[current] = set()
            continue
        if current and BLOCK_END.match(line):
            current = None
            continue
        if current:
            key = KEY_LINE.match(line)
            if key:
                locales[current].add(key.group(1))

    return locales


def main() -> int:
    locales = parse(I18N)

    if REFERENCE not in locales:
        print(f"FAIL: no '{REFERENCE}' block found in i18n.ts", file=sys.stderr)
        return 1

    reference = locales[REFERENCE]
    if not reference:
        print(f"FAIL: '{REFERENCE}' block is empty", file=sys.stderr)
        return 1

    print(f"Reference locale '{REFERENCE}': {len(reference)} keys")

    failed = False
    for lang, keys in sorted(locales.items()):
        if lang == REFERENCE:
            continue

        missing = sorted(reference - keys)
        extra = sorted(keys - reference)

        if missing:
            failed = True
            print(f"FAIL  {lang}: {len(missing)} missing key(s)")
            for key in missing:
                print(f"        - {key}")
        else:
            print(f"OK    {lang}: {len(keys)} keys")

        # Extra keys are not fatal — an untranslated string falls back to
        # English and the app still works. But they are usually a typo.
        if extra:
            print(f"WARN  {lang}: {len(extra)} key(s) not in {REFERENCE}: {extra}")

    if failed:
        print("\nAdd the missing keys to web/src/lib/i18n.ts.")
        print("A missing key silently falls back to English, which on a")
        print("Khortha-speaking farmer's phone reads as a broken app.")
        return 1

    print("\nAll locales complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
