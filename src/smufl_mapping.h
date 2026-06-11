/*
 * Copyright (C) 2025, Robert Patterson
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */
#pragma once

#include <string_view>
#include <optional>
#include <vector>

namespace smufl_mapping {

/// @enum SmuflGlyphSource
/// @brief Known sources for SMuFL glyphs
enum class SmuflGlyphSource
{
    Smufl,      ///< standard glyphs (the default: keep it first)
    Finale,     ///< optional glyphs defined by MakeMusic for Finale SMuFL fonts
    Bravura,    ///< optional glyphs in Bravura
    Other       ///< optional glyphs from other source
};

/// @struct SmuflGlyphInfo
/// @brief Describes a SMuFL glyph.
struct SmuflGlyphInfo
{
    char32_t codepoint{};           ///< The Unicode codepoint
    std::string_view description;   ///< The glyph description
    SmuflGlyphSource source{};      ///< The source for the glyph
};

/// @struct LegacyGlyphInfo
/// @brief Maps a SMuFL glyph to a legacy codepoint.
struct LegacyGlyphInfo
{
    std::string_view name{};                ///< e.g., "tremolo1"
    std::optional<char32_t> codepoint{};    ///< The SMuFL codepoint, if known (nullopt means unspecified)
    std::string_view description{};         ///< Since this field is usually empty, you can use `getGlyphInfo(name, source)`
                                            ///< to get the associated #SmuflGlyphInfo for this glyph. That contains the glyph description.
    SmuflGlyphSource source{};              ///< The source for this SMuFL glyph
    bool alternate{false};                  ///< True if this entry reflects an alternate/non-canonical mapping.
};

/// @brief Look up a glyph name in the standard set, falling back to an optional glyph set if provided.
/// @param name The SMuFL glyph name to look up (e.g., "gClef", "braceLarge").
/// @param optionalSource If specified, and the name is not found in the standard glyph set,
///        search the optional glyph set for the given source (e.g., Bravura, Finale).
/// @return Pointer to GlyphInfo if found; nullptr otherwise.
const SmuflGlyphInfo* getGlyphInfo(std::string_view name,
                                   std::optional<SmuflGlyphSource> optionalSource = std::nullopt);

/// @brief Look up the SMuFL glyph name associated with a given codepoint.
/// @param codepoint The Unicode codepoint (e.g., 0xE050).
/// @param optionalSource If provided, and the codepoint is not found in the standard set,
///        search the optional glyphs for the specified source.
/// @return Pointer to glyph name (`std::string_view`) if found, or nullptr.
const std::string_view* getGlyphName(char32_t codepoint,
                                     std::optional<SmuflGlyphSource> optionalSource = std::nullopt);

/// @brief Look up the SMuFL glyph name for either a SMuFL font or a legacy music font.
/// @param fontName The font name, used when `fontIsSmufl` is false.
/// @param codepoint The encoded character to look up.
/// @param fontIsSmufl True when `codepoint` is already a SMuFL codepoint in a SMuFL font.
/// @param optionalSource If provided for a SMuFL font, search that optional glyph set after the standard set.
/// @return Pointer to glyph name (`std::string_view`) if found, or nullptr.
const std::string_view* getGlyphNameForFont(std::string_view fontName,
                                            char32_t codepoint,
                                            bool fontIsSmufl,
                                            std::optional<SmuflGlyphSource> optionalSource = std::nullopt);

/// @brief Lookup legacy glyph info by font name and codepoint.
/// @param fontName The name of the legacy font (e.g., "maestro", "petrucci"). This is a case-insensitive search.
/// @param codepoint The legacy font codepoint to search for. (Commonly in the 0x00..0xFF range, but may be larger).
/// @return A pointer to the LegacyGlyphInfo, or nullptr if not found.
const LegacyGlyphInfo* getLegacyGlyphInfo(std::string_view fontName, char32_t codepoint);

/// @brief Return every legacy glyph mapping for a font/codepoint.
/// @param fontName Legacy font name (case-insensitive, whitespace ignored).
/// @param codepoint Legacy codepoint to look up.
/// @return Vector of pointers; canonical entries appear first when present.
std::vector<const LegacyGlyphInfo*> getAllLegacyGlyphInfo(std::string_view fontName,
                                                          char32_t codepoint);

} // namespace smufl_mapping
