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

#include <gtest/gtest.h>
#include "smufl_mapping.h"

using namespace smufl_mapping;

TEST(LegacyGlyphInfoTests, KnownGlyphLookup)
{
    {
        auto* info = getLegacyGlyphInfo("maestro", 207);
        ASSERT_NE(info, nullptr);
        EXPECT_EQ(info->name, "noteheadBlack");
        EXPECT_EQ(info->codepoint, 0xE0A4);
        EXPECT_EQ(info->source, SmuflGlyphSource::Smufl);
    }
    {
        auto* info = getLegacyGlyphInfo("Jazz", 103);
        EXPECT_EQ(info->name, "arpeggioVerticalSegment");
        EXPECT_EQ(info->codepoint, 0xF700);
        EXPECT_EQ(info->source, SmuflGlyphSource::Finale);
    }
}

TEST(LegacyGlyphInfoTests, CaseInsensitiveFontName)
{
    auto* info = getLegacyGlyphInfo("ChacOnNe", 65);
    ASSERT_NE(info, nullptr);
    EXPECT_EQ(info->name, "accidentalFlatParens");
    EXPECT_EQ(info->codepoint, 0xF5D5);
    EXPECT_EQ(info->source, SmuflGlyphSource::Finale);
}

TEST(LegacyGlyphInfoTests, IgnoresSpacesInFontName)
{
    auto* compact = getLegacyGlyphInfo("FinaleCopyistText", 123);
    ASSERT_NE(compact, nullptr);
    EXPECT_EQ(compact->name, "enclosureBracketLeft");
    EXPECT_EQ(compact->codepoint, 0xF720);

    auto* spaced = getLegacyGlyphInfo("Finale Copyist Text", 123);
    ASSERT_NE(spaced, nullptr);
    EXPECT_EQ(spaced->name, "enclosureBracketLeft");
    EXPECT_EQ(spaced->codepoint, 0xF720);
}

TEST(LegacyGlyphInfoTests, UnknownFont)
{
    auto* info = getLegacyGlyphInfo("unknownfont", 0xF000);
    EXPECT_EQ(info, nullptr);
}

TEST(LegacyGlyphInfoTests, UnknownCodepoint)
{
    // Assuming 0xFFFF isn't mapped in "maestro"
    auto* info = getLegacyGlyphInfo("maestro", 0xFFFF);
    EXPECT_EQ(info, nullptr);
}

TEST(LegacyGlyphInfoTests, CollisionPrefersFirstCanonicalEntry)
{
    auto* info = getLegacyGlyphInfo("maestro", 45);
    ASSERT_NE(info, nullptr);
    EXPECT_EQ(info->name, "articTenutoAbove");
    EXPECT_EQ(info->codepoint, 0xE4A4);
}

TEST(LegacyGlyphInfoTests, CanonicalPreferenceWithMixedEntries)
{
    auto* info = getLegacyGlyphInfo("maestro", 43);
    ASSERT_NE(info, nullptr);
    EXPECT_EQ(info->name, "brassMuteClosed");
    EXPECT_FALSE(info->alternate);

    auto infos = getAllLegacyGlyphInfo("maestro", 43);
    ASSERT_EQ(infos.size(), 3u);
    EXPECT_FALSE(infos[0]->alternate);
    EXPECT_TRUE(infos[1]->alternate);
    EXPECT_TRUE(infos[2]->alternate);
}

TEST(LegacyGlyphInfoTests, CollisionSkipsAlternateEntry)
{
    auto* info = getLegacyGlyphInfo("Broadway Copyist", 246);
    ASSERT_NE(info, nullptr);
    EXPECT_EQ(info->name, "csymAugmented");
    EXPECT_EQ(info->codepoint, 0xE872);
}

TEST(LegacyGlyphInfoTests, GetAllReturnsCanonicalThenAlternate)
{
    auto infos = getAllLegacyGlyphInfo("Broadway Copyist", 246);
    ASSERT_EQ(infos.size(), 3u);
    EXPECT_EQ(infos[0]->name, "csymAugmented");
    EXPECT_FALSE(infos[0]->alternate);
    EXPECT_EQ(infos[1]->name, "timeSigPlus");
    EXPECT_FALSE(infos[1]->alternate);
    EXPECT_TRUE(infos[2]->alternate);
    EXPECT_EQ(infos[2]->name, "brassMuteClosed");
}

TEST(LegacyGlyphInfoTests, GetAllReturnsAllCanonicalEntries)
{
    auto infos = getAllLegacyGlyphInfo("maestro", 45);
    ASSERT_EQ(infos.size(), 2u);
    EXPECT_EQ(infos[0]->name, "articTenutoAbove");
    EXPECT_EQ(infos[1]->name, "articTenutoBelow");
    EXPECT_FALSE(infos[0]->alternate);
    EXPECT_FALSE(infos[1]->alternate);
}

TEST(LegacyGlyphInfoTests, GetAllHandlesUnknownFontOrCodepoint)
{
    auto emptyFont = getAllLegacyGlyphInfo("unknown-font", 0x1234);
    EXPECT_TRUE(emptyFont.empty());

    auto emptyCodepoint = getAllLegacyGlyphInfo("maestro", 0xFFFF);
    EXPECT_TRUE(emptyCodepoint.empty());
}

TEST(LegacyGlyphInfoTests, GetAllFontNormalizationMatchesCanonicalLookup)
{
    auto normalized = getAllLegacyGlyphInfo("FinaleCopyistText", 123);
    auto spaced = getAllLegacyGlyphInfo("Finale Copyist Text", 123);
    ASSERT_EQ(normalized.size(), spaced.size());
    for (std::size_t i = 0; i < normalized.size(); ++i) {
        EXPECT_EQ(normalized[i], spaced[i]);
    }
}

TEST(LegacyGlyphInfoTests, GetLegacyInfoFallsBackToAlternateWhenNoCanonical)
{
    // Legacy slot 65 in Broadway Copyist Percussion only has an alternate entry.
    auto* info = getLegacyGlyphInfo("Broadway Copyist Perc", 65);
    ASSERT_NE(info, nullptr);
    EXPECT_TRUE(info->alternate);

    auto infos = getAllLegacyGlyphInfo("Broadway Copyist Perc", 65);
    ASSERT_EQ(infos.size(), 1u);
    EXPECT_TRUE(infos[0]->alternate);
}

TEST(LegacyFontInfoTests, ReturnsMeasuredSizeForEngravingFont)
{
    auto info = getLegacyFontInfo("Maestro");
    ASSERT_TRUE(info.has_value());
    EXPECT_EQ(info->fontType, MusicFontType::Engraving);
    ASSERT_TRUE(info->staffSpacesPerEm.has_value());
    EXPECT_DOUBLE_EQ(*info->staffSpacesPerEm, 4.0);

    // Maestro spans the same four staff spaces per em that SMuFL defines, so a
    // point size carries over to a substituted SMuFL font unchanged.
    ASSERT_TRUE(info->smuflSizeRatio().has_value());
    EXPECT_DOUBLE_EQ(*info->smuflSizeRatio(), 1.0);
}

TEST(LegacyFontInfoTests, ReportsTextFonts)
{
    auto info = getLegacyFontInfo("JazzText");
    ASSERT_TRUE(info.has_value());
    EXPECT_EQ(info->fontType, MusicFontType::Text);
}

TEST(LegacyFontInfoTests, FontNameNormalizationMatchesGlyphLookup)
{
    auto spaced = getLegacyFontInfo("Maestro Wide");
    auto squashed = getLegacyFontInfo("maestrowide");
    auto mixedCase = getLegacyFontInfo("  MAESTRO   wide ");
    ASSERT_TRUE(spaced.has_value());
    ASSERT_TRUE(squashed.has_value());
    ASSERT_TRUE(mixedCase.has_value());
    EXPECT_EQ(spaced->staffSpacesPerEm, squashed->staffSpacesPerEm);
    EXPECT_EQ(spaced->staffSpacesPerEm, mixedCase->staffSpacesPerEm);
}

TEST(LegacyFontInfoTests, OptedOutFontIsDistinctFromUnknownFont)
{
    // Patmm's glyphs yield no coherent scale, so it opts out of size mapping.
    // That is a known font with no size, not an unknown font.
    auto optedOut = getLegacyFontInfo("Patmm");
    ASSERT_TRUE(optedOut.has_value());
    EXPECT_FALSE(optedOut->staffSpacesPerEm.has_value());
    EXPECT_FALSE(optedOut->smuflSizeRatio().has_value());
    EXPECT_FALSE(optedOut->sizeNotes.empty()) << "an opt-out must record why";

    EXPECT_FALSE(getLegacyFontInfo("no-such-font").has_value());
}

TEST(LegacyFontInfoTests, EveryMappedFontIsQueryable)
{
    // Guards against the generator dropping metadata for a font: every font that
    // resolves a glyph must also resolve font-level info.
    for (const auto& fontName : { "Maestro", "Petrucci", "Jazz", "Engraver Font Set",
                                  "Broadway Copyist", "Pmusic", "Tamburo", "MaestroTimes" }) {
        auto info = getLegacyFontInfo(fontName);
        ASSERT_TRUE(info.has_value()) << fontName;
        if (info->staffSpacesPerEm) {
            EXPECT_GT(*info->staffSpacesPerEm, 0.0) << fontName;
        } else {
            EXPECT_FALSE(info->sizeNotes.empty()) << fontName;
        }
    }
}

TEST(LegacyFontInfoTests, ReportsSmuflSuccessorFont)
{
    auto maestro = getLegacyFontInfo("Maestro");
    ASSERT_TRUE(maestro.has_value());
    EXPECT_EQ(maestro->smuflSuccessorFont, "Finale Maestro");

    auto petrucci = getLegacyFontInfo("Petrucci");
    ASSERT_TRUE(petrucci.has_value());
    EXPECT_EQ(petrucci->smuflSuccessorFont, "Finale Legacy");
}

TEST(LegacyFontInfoTests, TextFontNamesTextSuccessorWhereOneExists)
{
    // A text font substitutes a SMuFL text face so the glyph keeps text metrics,
    // even though these outlines were also reused into the music face.
    auto jazzText = getLegacyFontInfo("JazzText");
    ASSERT_TRUE(jazzText.has_value());
    EXPECT_EQ(jazzText->fontType, MusicFontType::Text);
    EXPECT_EQ(jazzText->smuflSuccessorFont, "Finale Jazz Text");

    auto jazz = getLegacyFontInfo("Jazz");
    ASSERT_TRUE(jazz.has_value());
    EXPECT_EQ(jazz->fontType, MusicFontType::Engraving);
    EXPECT_EQ(jazz->smuflSuccessorFont, "Finale Jazz");
}

TEST(LegacyFontInfoTests, UnestablishedSuccessorIsEmptyAndExplained)
{
    auto info = getLegacyFontInfo("Rentaro");
    ASSERT_TRUE(info.has_value());
    EXPECT_TRUE(info->smuflSuccessorFont.empty());
    EXPECT_FALSE(info->successorNotes.empty())
        << "an unestablished successor must record why";
}

TEST(LegacyFontInfoTests, SuccessorAndSizeAreIndependent)
{
    // The two fields answer different questions and must not be conflated.
    // Pmusic has a successor by deliberate substitution despite sharing no
    // design, Kousaku has a measured size but no established successor, and
    // Rentaro has neither.
    auto pmusic = getLegacyFontInfo("Pmusic");
    ASSERT_TRUE(pmusic.has_value());
    EXPECT_FALSE(pmusic->smuflSuccessorFont.empty());
    EXPECT_TRUE(pmusic->staffSpacesPerEm.has_value());

    auto kousaku = getLegacyFontInfo("Kousaku");
    ASSERT_TRUE(kousaku.has_value());
    EXPECT_TRUE(kousaku->smuflSuccessorFont.empty());
    EXPECT_TRUE(kousaku->staffSpacesPerEm.has_value());

    auto rentaro = getLegacyFontInfo("Rentaro");
    ASSERT_TRUE(rentaro.has_value());
    EXPECT_TRUE(rentaro->smuflSuccessorFont.empty());
    EXPECT_FALSE(rentaro->staffSpacesPerEm.has_value());
}

TEST(LegacyFontInfoTests, StyleIsIndependentOfType)
{
    // The two axes are orthogonal: a font may be handwritten and still be set
    // inline with text, so neither field can be derived from the other.
    auto jazz = getLegacyFontInfo("Jazz");
    ASSERT_TRUE(jazz.has_value());
    EXPECT_EQ(jazz->fontType, MusicFontType::Engraving);
    EXPECT_EQ(jazz->fontStyle, MusicFontStyle::Handwritten);

    auto jazzText = getLegacyFontInfo("JazzText");
    ASSERT_TRUE(jazzText.has_value());
    EXPECT_EQ(jazzText->fontType, MusicFontType::Text);
    EXPECT_EQ(jazzText->fontStyle, MusicFontStyle::Handwritten);

    auto maestro = getLegacyFontInfo("Maestro");
    ASSERT_TRUE(maestro.has_value());
    EXPECT_EQ(maestro->fontType, MusicFontType::Engraving);
    EXPECT_EQ(maestro->fontStyle, MusicFontStyle::Engraved);

    auto maestroTimes = getLegacyFontInfo("MaestroTimes");
    ASSERT_TRUE(maestroTimes.has_value());
    EXPECT_EQ(maestroTimes->fontType, MusicFontType::Text);
    EXPECT_EQ(maestroTimes->fontStyle, MusicFontStyle::Engraved);
}

TEST(LegacyFontInfoTests, MetadataOnlyFontResolvesWithoutGlyphs)
{
    // Sonata and Ash Music have no glyph mappings, but a caller substituting a
    // modern face still needs their successor. Font-level lookup must succeed
    // while every glyph lookup correctly finds nothing.
    for (const auto& [fontName, successor] :
         { std::pair<std::string_view, std::string_view>{ "Sonata", "Finale Maestro" },
           std::pair<std::string_view, std::string_view>{ "Ash Music", "Finale Ash" } }) {
        auto info = getLegacyFontInfo(fontName);
        ASSERT_TRUE(info.has_value()) << fontName;
        EXPECT_EQ(info->smuflSuccessorFont, successor) << fontName;
        EXPECT_TRUE(info->staffSpacesPerEm.has_value()) << fontName;

        EXPECT_EQ(getLegacyGlyphInfo(fontName, 65), nullptr) << fontName;
        EXPECT_TRUE(getAllLegacyGlyphInfo(fontName, 65).empty()) << fontName;
    }
}

TEST(SmuflFontInfoTests, ReportsTypeStyleAndSize)
{
    auto bravura = getSmuflFontInfo("Bravura");
    ASSERT_TRUE(bravura.has_value());
    EXPECT_EQ(bravura->fontType, MusicFontType::Engraving);
    EXPECT_EQ(bravura->fontStyle, MusicFontStyle::Engraved);
    ASSERT_TRUE(bravura->staffSpacesPerEm.has_value());
    EXPECT_DOUBLE_EQ(*bravura->staffSpacesPerEm, kSmuflStaffSpacesPerEm);

    auto petaluma = getSmuflFontInfo("Petaluma");
    ASSERT_TRUE(petaluma.has_value());
    EXPECT_EQ(petaluma->fontStyle, MusicFontStyle::Handwritten);

    EXPECT_FALSE(getSmuflFontInfo("Not A Real Font").has_value());
}

TEST(SmuflFontInfoTests, TextFontsDoNotAllShareOneConvention)
{
    // The whole reason this is recorded rather than assumed: Bravura Text uses
    // five staff spaces per em while MakeMusic's text faces stay on the music
    // em scale at four. Assuming either one mis-sizes the other by 25%.
    auto bravuraText = getSmuflFontInfo("Bravura Text");
    ASSERT_TRUE(bravuraText.has_value());
    EXPECT_EQ(bravuraText->fontType, MusicFontType::Text);
    ASSERT_TRUE(bravuraText->staffSpacesPerEm.has_value());
    EXPECT_DOUBLE_EQ(*bravuraText->staffSpacesPerEm, 5.0);

    auto maestroText = getSmuflFontInfo("Finale Maestro Text");
    ASSERT_TRUE(maestroText.has_value());
    EXPECT_EQ(maestroText->fontType, MusicFontType::Text);
    ASSERT_TRUE(maestroText->staffSpacesPerEm.has_value());
    EXPECT_DOUBLE_EQ(*maestroText->staffSpacesPerEm, 4.0);
}

TEST(SmuflFontInfoTests, FontNameNormalizationMatchesLegacyLookup)
{
    auto spaced = getSmuflFontInfo("Finale Maestro Text");
    auto squashed = getSmuflFontInfo("finalemaestrotext");
    auto mixed = getSmuflFontInfo("  FINALE  Maestro   TEXT ");
    ASSERT_TRUE(spaced.has_value());
    ASSERT_TRUE(squashed.has_value());
    ASSERT_TRUE(mixed.has_value());
    EXPECT_EQ(spaced->staffSpacesPerEm, squashed->staffSpacesPerEm);
    EXPECT_EQ(spaced->staffSpacesPerEm, mixed->staffSpacesPerEm);
}

TEST(SmuflFontInfoTests, EverySuccessorResolvesInTheRegistry)
{
    // The validator enforces this at build time; assert it holds at runtime too,
    // so a caller can follow smuflSuccessorFont without a null check.
    for (const auto& fontName : { "Maestro", "Petrucci", "Jazz", "JazzText", "Chaconne",
                                  "Sonata", "Ash Music", "Broadway Copyist Text",
                                  "Finale Copyist Text", "MaestroTimes", "Engraver Time" }) {
        auto legacy = getLegacyFontInfo(fontName);
        ASSERT_TRUE(legacy.has_value()) << fontName;
        ASSERT_FALSE(legacy->smuflSuccessorFont.empty()) << fontName;
        EXPECT_TRUE(getSmuflFontInfo(legacy->smuflSuccessorFont).has_value())
            << fontName << " -> " << legacy->smuflSuccessorFont;
    }
}
