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
#include <unordered_map>
#include <algorithm>
#include <string>
#include <cctype>

#include "smufl_mapping.h"

#include "detail/glyphnames_smufl.h"
#include "detail/glyphnames_finale.h"
#include "detail/glyphnames_bravura.h"
#include "detail/glyphnames_legacy.h"

namespace smufl_mapping {

#ifndef DOXYGEN_SHOULD_IGNORE_THIS
template <typename Key, typename Pair>
static constexpr const typename Pair::second_type* binarySearchByKey(
    const Key& key,
    const Pair* table,
    std::size_t size) noexcept
{
    std::size_t low = 0;
    std::size_t high = size;

    while (low < high) {
        std::size_t mid = low + (high - low) / 2;
        const auto& pair = table[mid];

        if (pair.first < key) {
            low = mid + 1;
        } else if (key < pair.first) {
            high = mid;
        } else {
            return &pair.second;
        }
    }

    return nullptr;
}

template <typename Key, typename Pair, std::size_t N>
static constexpr const typename Pair::second_type* binarySearchByKey(
    const Key& key,
    const Pair (&table)[N]) noexcept
{
    return binarySearchByKey<Key, Pair>(key, table, N);
}
#endif // DOXYGEN_SHOULD_IGNORE_THIS

const SmuflGlyphInfo* getGlyphInfo(std::string_view name,
                                   std::optional<SmuflGlyphSource> optionalSource)
{
    // Step 1: Search standard set (glyphnamesSmufl)
    if (const SmuflGlyphInfo* info = binarySearchByKey(name, detail::glyphnamesSmufl)) {
        return info;
    }

    // Step 2: If a specific optional source is given, search only that
    if (optionalSource) {
        switch (*optionalSource) {
            case SmuflGlyphSource::Bravura:
                return binarySearchByKey(name, detail::glyphnamesBravura);
            case SmuflGlyphSource::Finale:
                return binarySearchByKey(name, detail::glyphnamesFinale);
            default:
                return nullptr;
        }
    }

    // Step 3: Not found
    return nullptr;
}

const std::string_view* getGlyphName(char32_t codepoint,
                                     std::optional<SmuflGlyphSource> optionalSource)
{
    // Step 1: Try standard glyph set
    if (const auto* name = binarySearchByKey(codepoint, detail::reverseGlyphnamesSmufl)) {
        return name;
    }

    // Step 2: If optional source is provided, search only that set
    if (optionalSource) {
        switch (*optionalSource) {
            case SmuflGlyphSource::Bravura:
                return binarySearchByKey(codepoint, detail::reverseGlyphnamesBravura);

            case SmuflGlyphSource::Finale:
                return binarySearchByKey(codepoint, detail::reverseGlyphnamesFinale);

            default:
                break;
        }
    }

    // Step 3: Not found
    return nullptr;
}

const std::string_view* getGlyphNameForFont(std::string_view fontName,
                                            char32_t codepoint,
                                            bool fontIsSmufl,
                                            std::optional<SmuflGlyphSource> optionalSource)
{
    if (fontIsSmufl) {
        return getGlyphName(codepoint, optionalSource);
    }

    if (const LegacyGlyphInfo* legacyInfo = getLegacyGlyphInfo(fontName, codepoint)) {
        return &legacyInfo->name;
    }

    return nullptr;
}

// Lowercase normalization for case-insensitive font name lookup.
// Also removes whitespace so font keys match regardless of platform naming differences.
static std::string normalizeFontKey(std::string_view s)
{
    std::string out;
    out.reserve(s.size());
    for (unsigned char c : s) {
        const bool isAsciiWhitespace = (c <= 0x7F) && std::isspace(c);
        if (isAsciiWhitespace) {
            continue;
        }
        out.push_back(static_cast<char>(std::tolower(c))); // normalize case
    }
    return out;
}

namespace {

const detail::LegacyFontMapping* findLegacyFont(std::string_view fontName)
{
    const auto normalizedFontName = normalizeFontKey(fontName);
    const std::string_view key(normalizedFontName);
    return binarySearchByKey(key, detail::legacyFontMappings);
}

const std::pair<char32_t, LegacyGlyphInfo>* findLegacyRange(
    const detail::LegacyFontMapping& mapping,
    char32_t codepoint,
    const std::pair<char32_t, LegacyGlyphInfo>** range_end)
{
    const auto* begin = mapping.table;
    const auto* end = begin + mapping.size;
    const auto* iter = std::lower_bound(
        begin,
        end,
        codepoint,
        [](const auto& lhs, char32_t rhs) { return lhs.first < rhs; });
    if (iter == end || iter->first != codepoint) {
        return nullptr;
    }
    const auto* upper = iter;
    while (upper != end && upper->first == codepoint) {
        ++upper;
    }
    if (range_end) {
        *range_end = upper;
    }
    return iter;
}

} // namespace

const LegacyGlyphInfo* getLegacyGlyphInfo(std::string_view fontName, char32_t codepoint)
{
    const auto* mapping = findLegacyFont(fontName);
    if (!mapping) {
        return nullptr;
    }

    const std::pair<char32_t, LegacyGlyphInfo>* range_end = nullptr;
    const auto* first_match = findLegacyRange(*mapping, codepoint, &range_end);
    if (!first_match) {
        return nullptr;
    }

    if (!first_match->second.alternate) {
        return &first_match->second;
    }

    for (auto* it = first_match + 1; it != range_end; ++it) {
        if (!it->second.alternate) {
            return &it->second;
        }
    }

    return &first_match->second;
}

std::vector<const LegacyGlyphInfo*> getAllLegacyGlyphInfo(std::string_view fontName,
                                                          char32_t codepoint)
{
    std::vector<const LegacyGlyphInfo*> results;

    const auto* mapping = findLegacyFont(fontName);
    if (!mapping) {
        return results;
    }

    const std::pair<char32_t, LegacyGlyphInfo>* range_end = nullptr;
    const auto* first = findLegacyRange(*mapping, codepoint, &range_end);
    if (!first) {
        return results;
    }

    for (auto* it = first; it != range_end; ++it) {
        if (!it->second.alternate) {
            results.push_back(&it->second);
        }
    }
    for (auto* it = first; it != range_end; ++it) {
        if (it->second.alternate) {
            results.push_back(&it->second);
        }
    }

    return results;
}

} // namespace smufl_mapping
