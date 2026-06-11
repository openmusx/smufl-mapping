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

#include "gtest/gtest.h"
#include "smufl_mapping.h"

using namespace smufl_mapping;

TEST(SmuflMappingTest, GetGlyphInfo_KnownName)
{
    {
        const SmuflGlyphInfo* info = getGlyphInfo("tremolo1");
        ASSERT_NE(info, nullptr);
        EXPECT_EQ(info->source, SmuflGlyphSource::Smufl);
        EXPECT_EQ(info->codepoint, 0xE220);
        EXPECT_EQ(info->description, "Combining tremolo 1");
    }
    {
        const SmuflGlyphInfo* info = getGlyphInfo("textEnclosureSegmentArrow");
        EXPECT_EQ(info, nullptr);
        info = getGlyphInfo("textEnclosureSegmentArrow", SmuflGlyphSource::Bravura);
        EXPECT_EQ(info, nullptr);
        info = getGlyphInfo("textEnclosureSegmentArrow", SmuflGlyphSource::Finale);
        ASSERT_NE(info, nullptr);
        EXPECT_EQ(info->source, SmuflGlyphSource::Finale);
        EXPECT_EQ(info->codepoint, 0xF813);
        EXPECT_EQ(info->description, "Text enclosure segment arrow");
    }
    {
        const SmuflGlyphInfo* info = getGlyphInfo("timeSigSlashLarge");
        EXPECT_EQ(info, nullptr);
        info = getGlyphInfo("timeSigSlashLarge", SmuflGlyphSource::Finale);
        EXPECT_EQ(info, nullptr);
        info = getGlyphInfo("timeSigSlashLarge", SmuflGlyphSource::Bravura);
        ASSERT_NE(info, nullptr);
        EXPECT_EQ(info->source, SmuflGlyphSource::Bravura);
        EXPECT_EQ(info->codepoint, 0xF503);
        EXPECT_EQ(info->description, "Time signature slash separator (outside staff)");
    }
}

TEST(SmuflMappingTest, GetGlyphInfo_UnknownName)
{
    const SmuflGlyphInfo* info = getGlyphInfo("4-string tab clef (serif)");
    EXPECT_EQ(info, nullptr);
}

TEST(SmuflMappingTest, GetGlyphInfoOptionalSourceScenarios)
{
    // Finale-only glyph should not be returned without specifying Finale.
    const SmuflGlyphInfo* info = getGlyphInfo("textEnclosureSegmentArrow");
    EXPECT_EQ(info, nullptr);
    info = getGlyphInfo("textEnclosureSegmentArrow", SmuflGlyphSource::Finale);
    ASSERT_NE(info, nullptr);

    // Bravura-only glyph should surface only when requesting Bravura.
    info = getGlyphInfo("timeSigSlashLarge");
    EXPECT_EQ(info, nullptr);
    info = getGlyphInfo("timeSigSlashLarge", SmuflGlyphSource::Bravura);
    ASSERT_NE(info, nullptr);

    // Asking for the wrong optional source yields nullptr.
    info = getGlyphInfo("timeSigSlashLarge", SmuflGlyphSource::Finale);
    EXPECT_EQ(info, nullptr);
}

TEST(SmuflMappingTest, GetGlyphName_KnownCodepoint)
{
    {
        auto name = getGlyphName(0xE220);
        ASSERT_TRUE(name);
        EXPECT_EQ(*name, "tremolo1");
    }
    {
        auto name = getGlyphName(0xF813);
        EXPECT_EQ(name, nullptr);
        name = getGlyphName(0xF813, SmuflGlyphSource::Bravura);
        EXPECT_EQ(name, nullptr);
        name = getGlyphName(0xF813, SmuflGlyphSource::Finale);
        ASSERT_TRUE(name);
        EXPECT_EQ(*name, "textEnclosureSegmentArrow");
    }
    {
        auto name = getGlyphName(0xF503);
        EXPECT_EQ(name, nullptr);
        name = getGlyphName(0xF503, SmuflGlyphSource::Finale);
        EXPECT_EQ(name, nullptr);
        name = getGlyphName(0xF503, SmuflGlyphSource::Bravura);
        ASSERT_TRUE(name);
        EXPECT_EQ(*name, "timeSigSlashLarge");
    }
}

TEST(SmuflMappingTest, GetGlyphName_UnknownCodepoint)
{
    auto name = getGlyphName(0xFFFF);
    EXPECT_FALSE(name);
}

TEST(SmuflMappingTest, GetGlyphNameOptionalSourceScenarios)
{
    // Finale-only codepoint requires the Finale source.
    auto name = getGlyphName(0xF813);
    EXPECT_EQ(name, nullptr);
    name = getGlyphName(0xF813, SmuflGlyphSource::Finale);
    ASSERT_TRUE(name);
    EXPECT_EQ(*name, "textEnclosureSegmentArrow");

    // Bravura-only codepoint requires the Bravura source.
    name = getGlyphName(0xF503);
    EXPECT_EQ(name, nullptr);
    name = getGlyphName(0xF503, SmuflGlyphSource::Bravura);
    ASSERT_TRUE(name);
    EXPECT_EQ(*name, "timeSigSlashLarge");

    // Wrong optional source should still be nullptr.
    name = getGlyphName(0xF503, SmuflGlyphSource::Finale);
    EXPECT_EQ(name, nullptr);
}

TEST(SmuflMappingTest, GetGlyphNameForFontSmuflFontUsesNeutralDefault)
{
    auto name = getGlyphNameForFont("Any SMuFL Font", 0xE220, true);
    ASSERT_TRUE(name);
    EXPECT_EQ(*name, "tremolo1");

    name = getGlyphNameForFont("Any SMuFL Font", 0xF813, true);
    EXPECT_EQ(name, nullptr);

    name = getGlyphNameForFont("Any SMuFL Font", 0xF813, true, SmuflGlyphSource::Finale);
    ASSERT_TRUE(name);
    EXPECT_EQ(*name, "textEnclosureSegmentArrow");
}

TEST(SmuflMappingTest, GetGlyphNameForFontLegacyFontUsesFontName)
{
    auto name = getGlyphNameForFont("Maestro", 62, false);
    ASSERT_TRUE(name);
    EXPECT_EQ(*name, "articAccentAbove");

    name = getGlyphNameForFont("Unknown Font", 62, false);
    EXPECT_EQ(name, nullptr);
}
