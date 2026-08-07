#!/usr/bin/env python3
"""
Checks that an unresolvable U+FFFD becomes nullopt rather than codepoint 0.

`LegacyGlyphInfo::codepoint` is a std::optional and nullopt is how it spells
"unspecified". A U+FFFD entry whose glyph name cannot be resolved through
glyphnamesFinale.json has no codepoint, so emitting 0 would produce an engaged
optional holding a codepoint no glyph occupies -- indistinguishable to a caller
from a real mapping.

Every U+FFFD entry in the current corpus resolves, so this path is latent. That
is exactly why it needs a test: nothing in the real data would reveal a
regression.
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT_DIR / "tools"
GENERATED_DIR = ROOT_DIR / "src" / "detail" / "legacy"

UNRESOLVABLE_GLYPH = "glyphNameThatIsNotInAnyReferenceList"


def load_generator():
    sys.path.insert(0, str(TOOLS_DIR))
    spec = importlib.util.spec_from_file_location(
        "generate_legacy_glyphnames_map", TOOLS_DIR / "generate_legacy_glyphnames_map.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_unresolved_becomes_nullopt(generator) -> list:
    fixture = {
        "fontMetadata": {"fontType": "engraving", "staffSpacesPerEm": 4.0},
        "glyphs": {
            UNRESOLVABLE_GLYPH: [
                {"legacyCodepoints": ["65"], "codepoint": "U+FFFD", "description": ""}
            ],
            "gClef": [
                {"legacyCodepoints": ["66"], "codepoint": "U+E050", "description": ""}
            ],
        },
    }

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        source = tmp_dir / "Synthetic Test Font.json"
        source.write_text(json.dumps(fixture, indent=4), encoding="utf-8")

        # Redirect output so the test never touches the checked-in headers.
        original_output_dir = generator.OUTPUT_DIR
        generator.OUTPUT_DIR = tmp_dir
        try:
            _, outpath, _, _ = generator.process_legacy_file(source, {}, {})
            emitted = outpath.read_text(encoding="utf-8")
        finally:
            generator.OUTPUT_DIR = original_output_dir

    failures = []
    unresolved_line = next(
        (line for line in emitted.splitlines() if UNRESOLVABLE_GLYPH in line), None
    )
    if unresolved_line is None:
        failures.append(
            "the unresolvable entry was dropped entirely; its glyph name is still "
            "known and should be emitted with a nullopt codepoint"
        )
    elif "std::nullopt" not in unresolved_line:
        failures.append(f"expected a nullopt codepoint, got: {unresolved_line.strip()}")

    resolved_line = next((line for line in emitted.splitlines() if "gClef" in line), None)
    if resolved_line is None or "0xE050" not in resolved_line:
        failures.append(f"a resolvable codepoint was not emitted normally: {resolved_line}")

    return failures


def check_empty_font_emits_no_array(generator) -> list:
    """A font with no glyph mappings must not emit a zero-length array.

    Zero-length arrays are a compiler extension that the project's
    -Wpedantic -Werror build rejects, so the generator emits no array at all and
    the master header pairs the font with a null table.
    """
    fixture = {
        "fontMetadata": {
            "fontType": "engraving",
            "fontStyle": "engraved",
            "smuflSuccessorFont": "Finale Maestro",
            "staffSpacesPerEm": 4.0,
        },
        "glyphs": {},
    }
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        source = tmp_dir / "Metadata Only Font.json"
        source.write_text(json.dumps(fixture, indent=4), encoding="utf-8")
        original_output_dir = generator.OUTPUT_DIR
        generator.OUTPUT_DIR = tmp_dir
        try:
            _, outpath, _, count = generator.process_legacy_file(source, {}, {})
            emitted = outpath.read_text(encoding="utf-8")
        finally:
            generator.OUTPUT_DIR = original_output_dir

    failures = []
    if count != 0:
        failures.append(f"expected 0 glyph entries, got {count}")
    if "[] = {" in emitted or "[] = {}" in emitted:
        failures.append("a zero-length array was emitted for a font with no glyphs")
    return failures


def check_no_zero_codepoints_in_generated_headers() -> list:
    # Guards the real corpus: a codepoint of 0 must never reach the tables.
    offenders = []
    for header in sorted(GENERATED_DIR.glob("*_legacy_map.h")):
        for number, line in enumerate(header.read_text(encoding="utf-8").splitlines(), 1):
            if ", 0x0," in line:
                offenders.append(f"{header.name}:{number}: {line.strip()}")
    return [f"codepoint 0 found in generated tables: {o}" for o in offenders[:5]]


def main() -> int:
    generator = load_generator()
    failures = check_unresolved_becomes_nullopt(generator)
    failures += check_empty_font_emits_no_array(generator)
    failures += check_no_zero_codepoints_in_generated_headers()

    if failures:
        print("FAIL: generated table contents are incorrect.", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print(
        "PASS: unresolved U+FFFD yields a nullopt codepoint, a font with no glyphs "
        "emits no array, and no table holds codepoint 0."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
