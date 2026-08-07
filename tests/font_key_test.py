#!/usr/bin/env python3
"""
Checks the Python half of the font-key contract.

Font-name normalization exists twice: normalizeFontKey() in
src/detail/font_key.h normalizes caller input at runtime, and
normalize_font_key() in tools/font_keys.py normalizes at generation time to mint
the table keys the C++ then searches. Neither can call the other in a build that
must work on a bare Python, so tests/data/font_key_vectors.json is the contract
they are both held to. If the two drift apart the generator can mint a key that
no runtime input is able to reach, and no other test would notice.

This covers the Python side and the freshness of the generated header;
tests/font_key_tests.cpp walks the same rows through the C++.
"""

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "tools"))

from font_keys import normalize_font_key  # noqa: E402
from generate_font_key_vectors import render  # noqa: E402

VECTOR_FILE = ROOT_DIR / "tests" / "data" / "font_key_vectors.json"
GENERATED_HEADER = ROOT_DIR / "tests" / "font_key_vectors.h"


def main() -> int:
    with VECTOR_FILE.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    vectors = data["vectors"]
    failures = []

    if not vectors:
        failures.append("the vector file is empty")

    for vector in vectors:
        raw, expected, note = vector["raw"], vector["key"], vector["note"]
        actual = normalize_font_key(raw)
        if actual != expected:
            failures.append(
                f"{raw!r} normalized to {actual!r}, expected {expected!r} ({note})"
            )
            continue

        # A key that does not survive a second pass would be unreachable through
        # the public lookups, which normalize whatever they are handed.
        again = normalize_font_key(expected)
        if again != expected:
            failures.append(
                f"{expected!r} is not idempotent: normalizing it again gives {again!r}"
            )

    # The header is checked in so that building the tests needs no Python. That
    # only holds if it actually matches the JSON it claims to come from.
    if GENERATED_HEADER.exists():
        current = GENERATED_HEADER.read_text(encoding="utf-8")
        expected_header = render(data)
        if current != expected_header:
            failures.append(
                f"{GENERATED_HEADER.relative_to(ROOT_DIR)} is stale; "
                "re-run tools/generate_font_key_vectors.py"
            )
    else:
        failures.append(
            f"{GENERATED_HEADER.relative_to(ROOT_DIR)} is missing; "
            "run tools/generate_font_key_vectors.py"
        )

    if failures:
        print("FAIL: font-key normalization did not match the shared vectors.", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"PASS: Python normalization matched all {len(vectors)} shared vectors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
