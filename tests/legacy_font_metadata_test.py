#!/usr/bin/env python3
"""
Checks the validator's handling of the fontMetadata block.

Mapping files are wrapped as {"fontMetadata": {...}, "glyphs": {...}}. The
wrapper exists so that font-level facts are distinguishable from glyph names:
under the older flat format a misspelled metadata key was indistinguishable from
a glyph name, so it could never be rejected. These cases lock that in, and
confirm that opting out of size mapping stays valid.
"""

import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT_DIR / "tools" / "validate_legacy_mappings.py"
DATA_DIR = Path(__file__).resolve().parent / "data"

# fixture -> (must_be_rejected, text that must appear in the message)
CASES = {
    "legacy_flat_shape.json": (True, "fontMetadata"),
    "legacy_unknown_metadata_key.json": (True, "unexpected fields"),
    "legacy_invalid_font_type.json": (True, "fontType"),
    "legacy_missing_successor.json": (True, "smuflSuccessorFont"),
    "legacy_missing_font_style.json": (True, "fontStyle"),
    "legacy_missing_provenance.json": (True, "provenance"),
    "legacy_invalid_provenance.json": (True, "provenance"),
    "legacy_size_optout.json": (False, ""),
}


def main() -> int:
    failures = []
    for fixture, (must_reject, expected_text) in CASES.items():
        path = DATA_DIR / fixture
        if not path.exists():
            failures.append(f"{fixture}: fixture is missing")
            continue

        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(path)],
            capture_output=True,
            text=True,
        )
        rejected = result.returncode != 0
        output = result.stdout + result.stderr

        if must_reject and not rejected:
            failures.append(f"{fixture}: validator accepted a file it must reject")
        elif not must_reject and rejected:
            failures.append(f"{fixture}: validator rejected a valid file:\n{output}")
        elif must_reject and expected_text not in output:
            # A file can be rejected for the wrong reason, which would leave the
            # case passing while no longer testing anything.
            failures.append(
                f"{fixture}: rejected, but the message never mentions "
                f"{expected_text!r}:\n{output}"
            )

    if failures:
        print("FAIL: fontMetadata validation did not behave as expected.", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(f"PASS: fontMetadata validation handled all {len(CASES)} cases correctly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
