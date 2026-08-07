#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set

from font_keys import normalize_font_key
from json_utils import DuplicateKeyError, load_json_strict


CODEPOINT_RE = re.compile(r"^U\+[0-9A-Fa-f]{4,6}$")
LEGACY_CODEPOINT_RE = re.compile(r"^(0x[0-9A-Fa-f]+|[0-9]+)$")
OFFSET_RE = re.compile(r"^-?[0-9]+$")
ALLOWED_KEYS = {
    "legacyCodepoints",
    "codepoint",
    "description",
    "nameIsMakeMusic",
    "smuflFontName",
    "xOffset",
    "yOffset",
    "alternate",
    "notes",
}

ALLOWED_METADATA_KEYS = {
    "fontType",
    "fontStyle",
    "smuflSuccessorFont",
    "successorNotes",
    "staffSpacesPerEm",
    "sizeNotes",
}

FONT_TYPES = {"engraving", "text"}
FONT_STYLES = {"engraved", "handwritten"}

ALLOWED_SMUFL_FONT_KEYS = {
    "fontType",
    "fontStyle",
    "staffSpacesPerEm",
    "sizeNotes",
}


BASE_DIR = Path(__file__).resolve().parent.parent
LEGACY_SCHEMA = BASE_DIR / "docs" / "legacy_mapping.schema.json"
REGISTRY_SCHEMA = BASE_DIR / "docs" / "smufl_font_registry.schema.json"


class ValidationError(Exception):
    pass


def _load_schema_validator(schema_path: Path):
    """Return a callable(instance, label) -> list[str], or None if unavailable.

    The JSON Schemas are the authoritative description of these files, so they
    are executed rather than left as prose that can drift from this script. But
    `jsonschema` is not a build dependency: regenerating headers must work on a
    bare Python, so when the module is missing we fall back to the hand-written
    checks below, which cover the same ground.
    """
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return None

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError:
        return None

    validator = jsonschema.Draft202012Validator(schema)

    def run(instance, label: str) -> List[str]:
        messages = []
        for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
            location = "/".join(str(p) for p in error.path) or "<root>"
            messages.append(f"{label}: schema violation at {location}: {error.message}")
        return messages

    return run


def _err(path: Path, glyph: str, entry_idx: int, message: str) -> ValidationError:
    prefix = f"{path}: glyph '{glyph}' entry {entry_idx}: {message}"
    return ValidationError(prefix)


def validate_entry(path: Path, glyph: str, entry_idx: int, entry: Dict) -> Set[str]:
    extra_keys = set(entry.keys()) - ALLOWED_KEYS
    if extra_keys:
        raise _err(path, glyph, entry_idx, f"unexpected fields: {sorted(extra_keys)}")

    if "legacyCodepoints" not in entry:
        raise _err(path, glyph, entry_idx, "missing 'legacyCodepoints'")
    legacy_values = entry["legacyCodepoints"]
    if not isinstance(legacy_values, list) or not legacy_values:
        raise _err(path, glyph, entry_idx, "'legacyCodepoints' must be a non-empty array")

    seen = set()
    for raw in legacy_values:
        if not isinstance(raw, str):
            raise _err(path, glyph, entry_idx, f"legacy codepoint '{raw}' must be a string")
        if not LEGACY_CODEPOINT_RE.match(raw):
            raise _err(
                path,
                glyph,
                entry_idx,
                f"legacy codepoint '{raw}' must be decimal or C-style hex",
            )
        if raw in seen:
            raise _err(path, glyph, entry_idx, f"duplicate legacy codepoint '{raw}'")
        seen.add(raw)

    codepoint = entry.get("codepoint")
    if not isinstance(codepoint, str) or not CODEPOINT_RE.match(codepoint):
        raise _err(path, glyph, entry_idx, "invalid or missing 'codepoint'")

    if "nameIsMakeMusic" in entry and not isinstance(entry["nameIsMakeMusic"], bool):
        raise _err(path, glyph, entry_idx, "'nameIsMakeMusic' must be a boolean")

    if "smuflFontName" in entry and not isinstance(entry["smuflFontName"], str):
        raise _err(path, glyph, entry_idx, "'smuflFontName' must be a string")

    for key in ("description", "notes"):
        if key in entry and not isinstance(entry[key], str):
            raise _err(path, glyph, entry_idx, f"'{key}' must be a string")

    for key in ("xOffset", "yOffset"):
        if key in entry:
            value = entry[key]
            if isinstance(value, int):
                entry[key] = str(value)
                value = entry[key]
            if not isinstance(value, str) or not OFFSET_RE.match(value):
                raise _err(path, glyph, entry_idx, f"'{key}' must be an integer string")

    if "alternate" in entry and not isinstance(entry["alternate"], bool):
        raise _err(path, glyph, entry_idx, "'alternate' must be a boolean")

    return seen


def validate_metadata(path: Path, metadata: Dict, warnings: List[str]) -> None:
    if not isinstance(metadata, dict):
        raise ValidationError(f"{path}: 'fontMetadata' must be an object")

    extra_keys = set(metadata.keys()) - ALLOWED_METADATA_KEYS
    if extra_keys:
        raise ValidationError(
            f"{path}: 'fontMetadata' has unexpected fields: {sorted(extra_keys)}"
        )

    if "fontType" not in metadata:
        raise ValidationError(f"{path}: 'fontMetadata' is missing 'fontType'")
    if metadata["fontType"] not in FONT_TYPES:
        raise ValidationError(
            f"{path}: 'fontType' must be one of {sorted(FONT_TYPES)}, "
            f"got {metadata['fontType']!r}"
        )

    # fontStyle is the font's appearance, independent of fontType's role: a font
    # may be handwritten and still be set inline with text.
    if "fontStyle" not in metadata:
        raise ValidationError(f"{path}: 'fontMetadata' is missing 'fontStyle'")
    if metadata["fontStyle"] not in FONT_STYLES:
        raise ValidationError(
            f"{path}: 'fontStyle' must be one of {sorted(FONT_STYLES)}, "
            f"got {metadata['fontStyle']!r}"
        )

    # Like staffSpacesPerEm, present-but-null is how the file says "no successor
    # established", so the key is required even when there is no value.
    if "smuflSuccessorFont" not in metadata:
        raise ValidationError(
            f"{path}: 'fontMetadata' is missing 'smuflSuccessorFont' "
            "(use null when no successor has been established)"
        )

    successor = metadata["smuflSuccessorFont"]
    if successor is not None:
        if not isinstance(successor, str) or not successor.strip():
            raise ValidationError(
                f"{path}: 'smuflSuccessorFont' must be a non-empty string or null"
            )

    if "successorNotes" in metadata and not isinstance(metadata["successorNotes"], str):
        raise ValidationError(f"{path}: 'successorNotes' must be a string")

    if successor is None and not metadata.get("successorNotes"):
        warnings.append(
            f"{path}: 'smuflSuccessorFont' is null without 'successorNotes'; "
            "record why no successor could be established"
        )

    # Present-but-null is how a font opts out of size mapping, so the key has to
    # be there even when there is no value: absent would be indistinguishable
    # from an oversight.
    if "staffSpacesPerEm" not in metadata:
        raise ValidationError(
            f"{path}: 'fontMetadata' is missing 'staffSpacesPerEm' "
            "(use null to opt out of size mapping)"
        )

    spaces = metadata["staffSpacesPerEm"]
    if spaces is not None:
        if isinstance(spaces, bool) or not isinstance(spaces, (int, float)):
            raise ValidationError(
                f"{path}: 'staffSpacesPerEm' must be a number or null"
            )
        if spaces <= 0:
            raise ValidationError(f"{path}: 'staffSpacesPerEm' must be greater than 0")

    if "sizeNotes" in metadata and not isinstance(metadata["sizeNotes"], str):
        raise ValidationError(f"{path}: 'sizeNotes' must be a string")

    if spaces is None and not metadata.get("sizeNotes"):
        warnings.append(
            f"{path}: 'staffSpacesPerEm' is null without 'sizeNotes'; "
            "record why the font opts out of size mapping"
        )


def validate_file(path: Path, warnings: List[str]) -> None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = load_json_strict(handle, location=str(path))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
    except DuplicateKeyError as exc:
        raise ValidationError(str(exc)) from exc

    if not isinstance(data, dict):
        raise ValidationError(f"{path}: top-level structure must be an object")

    unexpected = set(data.keys()) - {"fontMetadata", "glyphs"}
    if unexpected:
        # Before the fontMetadata/glyphs wrapper every top-level key was a glyph
        # name, so point at the migration rather than listing hundreds of keys.
        raise ValidationError(
            f"{path}: top level must contain only 'fontMetadata' and 'glyphs'; "
            f"found {len(unexpected)} other key(s) such as {sorted(unexpected)[:3]}. "
            "Files in the old flat format must be wrapped: "
            '{"fontMetadata": {...}, "glyphs": {<the previous contents>}}'
        )

    if "fontMetadata" not in data:
        raise ValidationError(f"{path}: missing required 'fontMetadata'")
    if "glyphs" not in data:
        raise ValidationError(f"{path}: missing required 'glyphs'")

    validate_metadata(path, data["fontMetadata"], warnings)

    glyphs = data["glyphs"]
    if not isinstance(glyphs, dict):
        raise ValidationError(f"{path}: 'glyphs' must be an object")

    for glyph, entries in glyphs.items():
        if not isinstance(glyph, str) or not glyph.strip():
            raise ValidationError(f"{path}: glyph names must be non-empty strings")

        if not isinstance(entries, list) or not entries:
            raise ValidationError(f"{path}: glyph '{glyph}' must map to a non-empty array")

        accumulated: Set[str] = set()
        for idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ValidationError(
                    f"{path}: glyph '{glyph}' entry {idx} must be an object"
                )
            if "legacyCodepoint" in entry:
                raise ValidationError(
                    f"{path}: glyph '{glyph}' entry {idx} uses deprecated 'legacyCodepoint'"
                )
            entry_codes = validate_entry(path, glyph, idx, entry)
            overlap = accumulated.intersection(entry_codes)
            if overlap:
                dup_list = ", ".join(sorted(overlap))
                raise ValidationError(
                    f"{path}: glyph '{glyph}' entry {idx} reuses legacy codepoint(s): {dup_list}"
                )
            accumulated.update(entry_codes)


def load_smufl_registry(path: Path) -> Dict:
    """Read and validate the SMuFL font registry."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = load_json_strict(handle, location=str(path))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc
    except DuplicateKeyError as exc:
        raise ValidationError(str(exc)) from exc

    if not isinstance(data, dict):
        raise ValidationError(f"{path}: top-level structure must be an object")

    for name, props in data.items():
        if not isinstance(name, str) or not name.strip():
            raise ValidationError(f"{path}: font names must be non-empty strings")
        if not isinstance(props, dict):
            raise ValidationError(f"{path}: '{name}' must map to an object")

        extra = set(props.keys()) - ALLOWED_SMUFL_FONT_KEYS
        if extra:
            raise ValidationError(f"{path}: '{name}' has unexpected fields: {sorted(extra)}")

        for key, allowed in (("fontType", FONT_TYPES), ("fontStyle", FONT_STYLES)):
            if key not in props:
                raise ValidationError(f"{path}: '{name}' is missing '{key}'")
            if props[key] not in allowed:
                raise ValidationError(
                    f"{path}: '{name}' has {key} {props[key]!r}; must be one of {sorted(allowed)}"
                )

        if "staffSpacesPerEm" not in props:
            raise ValidationError(
                f"{path}: '{name}' is missing 'staffSpacesPerEm' (use null when unestablished)"
            )
        spaces = props["staffSpacesPerEm"]
        if spaces is not None:
            if isinstance(spaces, bool) or not isinstance(spaces, (int, float)):
                raise ValidationError(f"{path}: '{name}' staffSpacesPerEm must be a number or null")
            if spaces <= 0:
                raise ValidationError(f"{path}: '{name}' staffSpacesPerEm must be greater than 0")

        if "sizeNotes" in props and not isinstance(props["sizeNotes"], str):
            raise ValidationError(f"{path}: '{name}' sizeNotes must be a string")

    return data


def check_successors_resolve(files: List[Path], registry: Dict) -> List[str]:
    """Every smuflSuccessorFont must name a font in the registry.

    Without this the field is an unvalidated free string, so a typo would
    silently produce a successor no client could ever resolve.
    """
    known = {normalize_font_key(name) for name in registry}
    errors = []
    for file_path in files:
        try:
            with file_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception:
            continue  # already reported by the per-file validation
        successor = (data.get("fontMetadata") or {}).get("smuflSuccessorFont")
        if successor and normalize_font_key(successor) not in known:
            errors.append(
                f"{file_path}: smuflSuccessorFont {successor!r} is not in the SMuFL font "
                f"registry; add it to source_json/smufl_fonts.json or correct the name"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate legacy JSON mapping files for smufl_mapping."
    )
    parser.add_argument(
        "--smufl-registry",
        type=Path,
        default=Path("source_json/smufl_fonts.json"),
        help="SMuFL font registry used to check smuflSuccessorFont values.",
    )
    parser.add_argument(
        "--legacy-dir",
        type=Path,
        default=Path("source_json/legacy"),
        help="Directory containing legacy JSON mapping files.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Optional explicit list of files to validate. Overrides --legacy-dir.",
    )
    args = parser.parse_args()

    if args.files:
        files = args.files
    else:
        files = sorted(args.legacy_dir.glob("*.json"))

    if not files:
        print("No legacy mapping files found.", file=sys.stderr)
        return 1

    errors: List[str] = []
    warnings: List[str] = []

    check_legacy_schema = _load_schema_validator(LEGACY_SCHEMA)
    if check_legacy_schema is None:
        print(
            "Note: the 'jsonschema' module is not installed, so the JSON Schemas were "
            "not executed; the equivalent hand-written checks still ran.",
            file=sys.stderr,
        )

    for file_path in files:
        try:
            validate_file(file_path, warnings)
        except ValidationError as exc:
            errors.append(str(exc))
            continue
        if check_legacy_schema:
            try:
                with file_path.open("r", encoding="utf-8") as handle:
                    errors.extend(check_legacy_schema(json.load(handle), str(file_path)))
            except Exception:
                pass  # malformed JSON was already reported above

    # The registry may be absent when validating an explicit file list in a test.
    if args.smufl_registry.exists():
        try:
            registry = load_smufl_registry(args.smufl_registry)
            errors.extend(check_successors_resolve(files, registry))
            check_registry_schema = _load_schema_validator(REGISTRY_SCHEMA)
            if check_registry_schema:
                errors.extend(check_registry_schema(registry, str(args.smufl_registry)))
        except ValidationError as exc:
            errors.append(str(exc))

    for msg in warnings:
        print(f"Warning: {msg}", file=sys.stderr)

    if errors:
        print("Legacy mapping validation failed:", file=sys.stderr)
        for msg in errors:
            print(f"  - {msg}", file=sys.stderr)
        return 1

    print(f"Validated {len(files)} legacy mapping file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
