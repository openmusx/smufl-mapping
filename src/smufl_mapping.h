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

/// @brief The number of staff spaces spanned by one em in a conforming SMuFL font.
///
/// SMuFL defines fonts so that one em equals four staff spaces, which is what makes a
/// point size portable from one SMuFL font to another. Legacy fonts make no such promise,
/// so #LegacyFontInfo::staffSpacesPerEm records what each legacy font actually does.
inline constexpr double kSmuflStaffSpacesPerEm = 4.0;

/// @enum MusicFontType
/// @brief How a music font is used in a score. Applies to both legacy and SMuFL fonts.
enum class MusicFontType
{
    Engraving,  ///< Placed in the score as notation
    Text        ///< Set inline with running text (chord symbols, metronome marks, expressions)
};

/// @enum MusicFontStyle
/// @brief What a music font looks like. Applies to both legacy and SMuFL fonts.
///
/// Independent of #MusicFontType: a font may be #Handwritten and still be set inline
/// with text, as the Jazz and Broadway Copyist text faces are.
enum class MusicFontStyle
{
    Engraved,   ///< Imitates traditional plate engraving
    Handwritten ///< Imitates manuscript
};

/// @struct SmuflFontInfo
/// @brief What is known about a SMuFL font.
struct SmuflFontInfo
{
    MusicFontType fontType{};                   ///< How the font is used in a score
    MusicFontStyle fontStyle{};                 ///< What the font looks like, independent of #fontType
    std::optional<double> staffSpacesPerEm{};   ///< Staff spaces spanned by one em.
                                                ///< A SMuFL *music* font is #kSmuflStaffSpacesPerEm by definition, but a
                                                ///< *text* font is not: Bravura Text and its peers use 5.0 while MakeMusic's
                                                ///< text faces stay on the music em scale at 4.0. A caller sizing a glyph
                                                ///< substituted into a text face must read this rather than assume.
                                                ///< `nullopt` when it could not be established.
    std::string_view sizeNotes{};               ///< Why #staffSpacesPerEm holds the value it does. Populated whenever the
                                                ///< value is `nullopt` or was not confirmed by measurement.
};

/// @struct LegacyFontInfo
/// @brief Font-level information about a legacy font as a whole.
struct LegacyFontInfo
{
    MusicFontType fontType{};                  ///< How the font is used in a score
    MusicFontStyle fontStyle{};                ///< What the font looks like, independent of #fontType
    std::string_view smuflSuccessorFont{};      ///< Name of the SMuFL font that supersedes this legacy font,
                                                ///< for a caller substituting a modern face. A #MusicFontType::Text
                                                ///< font names a SMuFL text face where one exists. Empty when no
                                                ///< successor has been established; callers should fall back to
                                                ///< their own default rather than guess.
    std::string_view successorNotes{};          ///< Why #smuflSuccessorFont holds the value it does. Populated
                                                ///< whenever it is empty or the choice is not obvious.
    std::optional<double> staffSpacesPerEm{};   ///< Staff spaces spanned by one em in this font.
                                                ///< `nullopt` means the font opts out: its point size has no
                                                ///< staff-relative meaning and callers must not derive a size from it.
    std::string_view sizeNotes{};               ///< Why #staffSpacesPerEm holds the value it does. Populated
                                                ///< whenever the value is `nullopt` or was inferred rather than measured.

    /// @brief The factor converting a point size in this legacy font to the equivalent
    ///        point size in a substituted SMuFL font.
    /// @return The factor, or `nullopt` when the font opts out of size mapping.
    ///
    /// Multiply the legacy font's point size by this value:
    /// @code
    /// if (auto ratio = info.smuflSizeRatio()) {
    ///     smuflPointSize = legacyPointSize * (*ratio);
    /// }
    /// @endcode
    constexpr std::optional<double> smuflSizeRatio() const
    {
        if (!staffSpacesPerEm) {
            return std::nullopt;
        }
        return kSmuflStaffSpacesPerEm / *staffSpacesPerEm;
    }
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

/// @brief Look up what is known about a SMuFL font.
/// @param fontName The SMuFL font name (e.g., "Bravura", "Finale Maestro Text"). The search is
///        case-insensitive and ignores whitespace.
/// @return The #SmuflFontInfo, or `nullopt` if the font is not in the registry.
///
/// Every name returned by #LegacyFontInfo::smuflSuccessorFont is guaranteed to resolve here;
/// the build fails otherwise.
std::optional<SmuflFontInfo> getSmuflFontInfo(std::string_view fontName);

/// @brief Look up font-level information for a legacy font.
/// @param fontName The name of the legacy font (e.g., "maestro", "petrucci"). The search is
///        case-insensitive and ignores whitespace.
/// @return The #LegacyFontInfo, or `nullopt` if the font is not a known legacy font.
///
/// A known font that opts out of size mapping returns an engaged #LegacyFontInfo whose
/// #LegacyFontInfo::staffSpacesPerEm is `nullopt`; that is distinct from an unknown font,
/// which returns `nullopt` here.
std::optional<LegacyFontInfo> getLegacyFontInfo(std::string_view fontName);

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
