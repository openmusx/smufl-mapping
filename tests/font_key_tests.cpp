/*
 * Copyright (C) 2026, Robert Patterson
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

#include <string>

#include "gtest/gtest.h"

#include "smufl_mapping.h"

#include "detail/font_key.h"
#include "font_key_vectors.h"

using namespace smufl_mapping;

// The generated table keys come from tools/font_keys.py, but every lookup at
// runtime goes through the C++ normalizer. If the two ever disagree the library
// can be handed a name that no key in the table can match, and nothing else in
// the suite would notice. These walk the shared vectors in
// tests/data/font_key_vectors.json; tests/font_key_test.py walks the same rows
// on the Python side.

TEST(FontKeyTests, MatchesSharedVectors)
{
    for (const auto& vector : test::fontKeyVectors) {
        EXPECT_EQ(detail::normalizeFontKey(vector.raw), std::string(vector.key))
            << "vector: " << vector.note;
    }
}

TEST(FontKeyTests, NormalizationIsIdempotent)
{
    // The generator normalizes a name once to mint a key. Were normalization not
    // idempotent, that key would itself normalize to something else and become
    // unreachable through the public lookups.
    for (const auto& vector : test::fontKeyVectors) {
        EXPECT_EQ(detail::normalizeFontKey(vector.key), std::string(vector.key))
            << "vector: " << vector.note;
    }
}

TEST(FontKeyTests, RawAndNormalizedSpellingsResolveAlike)
{
    // The same assertion as above, but reached through the public API, so it
    // also covers the binary search that consumes the normalized key. Vectors
    // naming no real font simply resolve to nullopt on both sides.
    for (const auto& vector : test::fontKeyVectors) {
        const auto rawLegacy = getLegacyFontInfo(vector.raw);
        const auto keyLegacy = getLegacyFontInfo(vector.key);
        ASSERT_EQ(rawLegacy.has_value(), keyLegacy.has_value())
            << "legacy lookup disagreed; vector: " << vector.note;
        if (rawLegacy && keyLegacy) {
            EXPECT_EQ(rawLegacy->staffSpacesPerEm, keyLegacy->staffSpacesPerEm)
                << "vector: " << vector.note;
            EXPECT_EQ(rawLegacy->smuflSuccessorFont, keyLegacy->smuflSuccessorFont)
                << "vector: " << vector.note;
        }

        const auto rawSmufl = getSmuflFontInfo(vector.raw);
        const auto keySmufl = getSmuflFontInfo(vector.key);
        ASSERT_EQ(rawSmufl.has_value(), keySmufl.has_value())
            << "SMuFL lookup disagreed; vector: " << vector.note;
        if (rawSmufl && keySmufl) {
            EXPECT_EQ(rawSmufl->staffSpacesPerEm, keySmufl->staffSpacesPerEm)
                << "vector: " << vector.note;
        }
    }
}

TEST(FontKeyTests, VectorsCoverRealFontsOnBothSides)
{
    // A guard on the vectors themselves: if every row named an unknown font,
    // RawAndNormalizedSpellingsResolveAlike would pass by comparing nullopt to
    // nullopt forever.
    int legacyHits = 0;
    int smuflHits = 0;
    for (const auto& vector : test::fontKeyVectors) {
        if (getLegacyFontInfo(vector.key)) {
            ++legacyHits;
        }
        if (getSmuflFontInfo(vector.key)) {
            ++smuflHits;
        }
    }
    EXPECT_GE(legacyHits, 3) << "vectors no longer exercise real legacy fonts";
    EXPECT_GE(smuflHits, 1) << "vectors no longer exercise a real SMuFL font";
}

TEST(FontKeyTests, CommaIsNotTreatedAsSeparator)
{
    // Called out on its own because it is the case most likely to be "fixed" by
    // someone widening the rule. A MusicXML font-family list must not collapse
    // into a single key: "Maestro, Times" would become "maestrotimes", the name
    // of a real Finale font, and the wrong face would be substituted silently.
    EXPECT_EQ(detail::normalizeFontKey("Maestro, Times"), std::string("maestro,times"));
    EXPECT_FALSE(getLegacyFontInfo("Maestro, Times").has_value());
    EXPECT_TRUE(getLegacyFontInfo("MaestroTimes").has_value());
}
