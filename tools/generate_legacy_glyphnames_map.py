#!/usr/bin/env python3

import sys
from datetime import datetime
from pathlib import Path

from font_keys import normalize_font_key
from json_utils import load_json_strict

BASE_DIR = Path(__file__).resolve().parent.parent  # root of repo
SOURCE_DIR = BASE_DIR / "source_json" / "legacy"
FINALE_FILE = BASE_DIR / "source_json" / "glyphnamesFinale.json"
BRAVURA_FILE = BASE_DIR / "source_json" / "glyphnamesBravura.json"
OUTPUT_DIR = BASE_DIR / "src" / "detail" / "legacy"
MASTER_HEADER = BASE_DIR / "src" / "detail" / "glyphnames_legacy.h"

def parse_codepoint(uplus: str) -> int:
    if not uplus.startswith("U+"):
        raise ValueError(f"Invalid codepoint format: {uplus}")
    return int(uplus[2:], 16)

def load_glyphnames(path):
    with path.open("r", encoding="utf-8") as f:
        data = load_json_strict(f, location=str(path))
    name_to_codepoint = {}
    for name, props in data.items():
        if "codepoint" in props:
            try:
                name_to_codepoint[name.strip()] = parse_codepoint(props["codepoint"])
            except Exception as e:
                print(f"Warning: Failed to parse codepoint for {name}: {e}")
    return name_to_codepoint

def sanitize_var_name(stem: str) -> str:
    parts = stem.replace("-", " ").replace("_", " ").split()
    return parts[0].lower() + ''.join(word.capitalize() for word in parts[1:])

def sanitize_file_name(stem: str) -> str:
    return stem.lower().replace("-", "_").replace(" ", "_")

FONT_TYPE_ENUM = {
    "engraving": "MusicFontType::Engraving",
    "text": "MusicFontType::Text",
}

FONT_STYLE_ENUM = {
    "engraved": "MusicFontStyle::Engraved",
    "handwritten": "MusicFontStyle::Handwritten",
}

def cpp_string_literal(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')

def process_legacy_file(path: Path, finale_map: dict, bravura_map: dict) -> tuple[str, Path, dict]:
    with path.open("r", encoding="utf-8") as f:
        data = load_json_strict(f, location=str(path))

    metadata = data["fontMetadata"]
    glyphs = data["glyphs"]

    fontname = path.stem
    varname = sanitize_var_name(fontname) + "LegacyGlyphs"
    outpath = OUTPUT_DIR / f"{sanitize_file_name(fontname)}_legacy_map.h"

    entries = []

    for glyphname, value in glyphs.items():
        glyphname = glyphname.strip()

        raw_entries = value if isinstance(value, list) else [value]

        for glyph_data in raw_entries:
            if not isinstance(glyph_data, dict):
                print(f"Unexpected entry type for '{glyphname}' in {path.name}; skipping")
                continue

            legacy_values = glyph_data.get("legacyCodepoints")
            if legacy_values is None:
                legacy_value = glyph_data.get("legacyCodepoint")
                if legacy_value is None:
                    print(f"Missing legacyCodepoints for '{glyphname}' in {path.name}")
                    continue
                legacy_values = [legacy_value]

            if not isinstance(legacy_values, list):
                legacy_values = [legacy_values]

            raw_codepoint = glyph_data.get("codepoint")
            description = glyph_data.get("description", "")
            smufl_font = glyph_data.get("smuflFontName", "finale").lower() # this is RGP proprietary in Lua mapping script: hopefully we can get something like it approved by SMuFL committee
            is_alternate = bool(glyph_data.get("alternate", False))

            # Resolve FFFD
            if raw_codepoint == "U+FFFD":
                resolved = finale_map.get(glyphname)
                if resolved:
                    codepoint = resolved
                    # print(f"Resolved 0xFFFD for {glyphname} → U+{resolved:04X}")
                else:
                    # LegacyGlyphInfo::codepoint is std::optional, and nullopt is
                    # how it spells "unspecified". Emitting 0 here would instead
                    # produce an engaged optional holding a codepoint that no
                    # glyph occupies, which callers cannot distinguish from a
                    # real mapping. The glyph name is still known and useful, so
                    # the entry is kept rather than dropped.
                    print(f"Could not resolve 0xFFFD for {glyphname}; emitting nullopt codepoint")
                    codepoint = None
            else:
                if not raw_codepoint:
                    print(f"Missing codepoint for '{glyphname}' in {path.name}; skipping")
                    continue
                try:
                    codepoint = parse_codepoint(raw_codepoint)
                except Exception:
                    print(f"Invalid codepoint '{raw_codepoint}' for '{glyphname}' in {path.name}; skipping")
                    continue

            # An unresolved codepoint is in no range at all, optional or standard.
            in_optional_range = codepoint is not None and 0xF400 <= codepoint <= 0xF8FF

            # Filter optional-range entries not in glyphnamesFinale
            if in_optional_range:
                target_map = bravura_map if smufl_font == "bravura" else finale_map
                if glyphname not in target_map:
                    print(f"Omitting optional-range glyph '{glyphname}' (not found in glyphnames{smufl_font.capitalize()})")
                    continue

            if in_optional_range:
                if smufl_font == "bravura":
                    source_enum = "SmuflGlyphSource::Bravura"
                else:
                    source_enum = "SmuflGlyphSource::Finale"
            else:
                source_enum = "SmuflGlyphSource::Smufl"

            for legacy_codepoint_str in legacy_values:
                if legacy_codepoint_str is None:
                    print(f"Missing legacyCodepoint entry for '{glyphname}' in {path.name}")
                    continue
                try:
                    legacy_codepoint = int(legacy_codepoint_str, 0)
                except ValueError:
                    print(f"Invalid legacyCodepoint '{legacy_codepoint_str}' for '{glyphname}' in {path.name}")
                    continue
                entries.append((legacy_codepoint, glyphname, codepoint, description, source_enum, is_alternate))

    # Emit C++ header
    entries.sort(key=lambda entry: entry[0])
    with outpath.open("w", encoding="utf-8") as out:
        out.write("// This file is generated from {}\n".format(path.name))
        out.write("//\n")
        out.write(f"// SPDX-FileCopyrightText: Generated by smufl_mapping ({datetime.now().year})\n")
        out.write("// SPDX-License-Identifier: MIT\n")
        out.write("//\n")
        out.write("// Source project: https://github.com/rpatters1/smufl-mapping\n")
        out.write("//\n")
        out.write("// This header was generated from SMuFL font metadata provided by SMuFL and Finale\n")
        out.write("// and is part of the internal implementation of the smufl_mapping project.\n")
        out.write("//\n")
        out.write("// To regenerate this file, run tools/generate_glyphnames_map.py\n")
        out.write('#pragma once\n\n')
        out.write('#include "smufl_mapping.h"\n\n')
        out.write('namespace smufl_mapping::detail::legacy {\n\n')
        if entries:
            out.write(f'constexpr std::pair<char32_t, LegacyGlyphInfo> {varname}[] = {{\n')
            for legacy_cp, gname, cp, desc, source, is_alternate in entries:
                desc_escaped = desc.replace('"', '\\"')
                alt_literal = "true" if is_alternate else "false"
                cp_literal = "std::nullopt" if cp is None else f"0x{cp:X}"
                out.write(f'    {{ {legacy_cp:3}, '
                        f'{{ "{gname}", {cp_literal}, "{desc_escaped}", {source}, {alt_literal} }} }},\n')
            out.write('};\n\n')
        else:
            # A metadata-only record: the font is known and has a successor, but no
            # glyph mappings exist for it. No array is emitted, because a zero-size
            # array is a compiler extension that -Wpedantic -Werror rejects; the
            # master header pairs this font with a null table instead.
            out.write(f'// {fontname} has no glyph mappings; see glyphnames_legacy.h.\n\n')
        out.write('} // namespace smufl_mapping::detail::legacy\n')

    return varname, outpath, metadata, len(entries)

from typing import List, Tuple
def emit_master_header(entries: List[Tuple[str, str, dict, int]]):
    # entries: list of (fontname, varname, metadata, glyph_count) tuples
    normalized_entries = [
        (fontname, varname, normalize_font_key(fontname), metadata, count)
        for fontname, varname, metadata, count in entries
    ]
    normalized_entries.sort(key=lambda item: item[2])
    outpath = MASTER_HEADER
    with outpath.open("w", encoding="utf-8") as out:
        out.write("// This file is auto-generated. Do not edit manually.\n")
        out.write("//\n")
        out.write(f"// SPDX-FileCopyrightText: Generated by smufl_mapping ({datetime.now().year})\n")
        out.write("// SPDX-License-Identifier: MIT\n")
        out.write("//\n")
        out.write("// Source project: https://github.com/rpatters1/smufl-mapping\n")
        out.write("//\n")
        out.write("// This header was generated from SMuFL font metadata provided by SMuFL and Finale\n")
        out.write("// and is part of the internal implementation of the smufl_mapping project.\n")
        out.write("//\n")
        out.write("// To regenerate this file, run tools/generate_glyphnames_map.py\n")
        out.write('#pragma once\n\n')
        out.write('#include "smufl_mapping.h"\n\n')

        for fontname, _, _, _, _ in normalized_entries:
            out.write(f'#include "detail/legacy/{sanitize_file_name(fontname)}_legacy_map.h"\n')

        out.write('\nnamespace smufl_mapping::detail {\n\n')

        out.write('struct LegacyFontMapping {\n')
        out.write('    const std::pair<char32_t, LegacyGlyphInfo>* table;\n')
        out.write('    std::size_t size;\n')
        out.write('    MusicFontType fontType;\n')
        out.write('    MusicFontStyle fontStyle;\n')
        out.write('    std::string_view smuflSuccessorFont;\n')
        out.write('    std::string_view successorNotes;\n')
        out.write('    std::optional<double> staffSpacesPerEm;\n')
        out.write('    std::string_view sizeNotes;\n')
        out.write('};\n\n')

        out.write('constexpr std::pair<std::string_view, LegacyFontMapping> legacyFontMappings[] = {\n')
        for fontname, varname, normalized_key, metadata, count in normalized_entries:
            font_type = FONT_TYPE_ENUM[metadata["fontType"]]
            font_style = FONT_STYLE_ENUM[metadata["fontStyle"]]
            table = (f'legacy::{varname}, std::size(legacy::{varname})'
                     if count else 'nullptr, 0')
            spaces = metadata["staffSpacesPerEm"]
            spaces_literal = "std::nullopt" if spaces is None else f"{float(spaces)!r}"
            # An absent successor is the empty string rather than another
            # optional: string_view is already nullable in the sense that
            # matters, and empty() reads the same at the call site.
            successor = cpp_string_literal(metadata.get("smuflSuccessorFont") or "")
            successor_notes = cpp_string_literal(metadata.get("successorNotes", ""))
            notes = cpp_string_literal(metadata.get("sizeNotes", ""))
            out.write(
                f'    {{ "{normalized_key}", {{{table}, '
                f'{font_type}, {font_style}, "{successor}", "{successor_notes}", '
                f'{spaces_literal}, "{notes}"}} }},\n'
            )
        out.write('};\n\n')

        out.write('} // namespace smufl_mapping::detail\n')

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    finale_map = load_glyphnames(FINALE_FILE)
    bravura_map = load_glyphnames(BRAVURA_FILE)

    all_entries = []
    for json_path in sorted(SOURCE_DIR.glob("*.json")):
        fontname = json_path.stem
        varname, _, metadata, count = process_legacy_file(json_path, finale_map, bravura_map)
        all_entries.append((fontname, varname, metadata, count))

    emit_master_header(all_entries)

if __name__ == "__main__":
    main()
