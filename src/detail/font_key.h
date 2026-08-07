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
#pragma once

#include <string>
#include <string_view>

namespace smufl_mapping::detail {

/// @brief Normalize a font name for lookup: fold ASCII case, drop ASCII whitespace.
///
/// Font names reach this library from score files, font menus and MusicXML, and
/// the same face is spelled differently in each ("Maestro Wide", "MaestroWide",
/// "MAESTRO WIDE"). Folding those to one key is what lets a single table entry
/// answer for all of them.
///
/// The rule is deliberately narrow, and everything it does *not* do is load
/// bearing:
///
/// * Only the six ASCII whitespace characters are removed. Nothing else is
///   treated as a separator — in particular a comma survives, which is what
///   stops a MusicXML `font-family` list such as "Maestro, Times" from being
///   welded into the single key "maestrotimes", the name of a real font.
/// * Only A-Z are lowercased, and non-ASCII bytes pass through untouched. This
///   is done with explicit ASCII arithmetic rather than std::tolower() so the
///   result cannot depend on the host program's locale: under a Latin-1 locale
///   std::tolower() will happily rewrite bytes in the middle of a UTF-8
///   sequence, which would make the same font name normalize two different ways
///   in two different processes.
///
/// `tools/font_keys.py` mirrors this byte for byte, and the two are pinned
/// together by `tests/data/font_key_vectors.json`. The Python side generates the
/// table keys this function is searched against, so if the two ever disagree the
/// library can be handed a name that no key in the table can match. Change one,
/// change the other, and add a vector.
inline std::string normalizeFontKey(std::string_view s)
{
    std::string out;
    out.reserve(s.size());
    for (unsigned char c : s) {
        // Space plus U+0009-U+000D: tab, newline, vertical tab, form feed,
        // carriage return. Matches std::isspace() in the "C" locale.
        if (c == ' ' || (c >= 0x09 && c <= 0x0D)) {
            continue;
        }
        if (c >= 'A' && c <= 'Z') {
            c = static_cast<unsigned char>(c - 'A' + 'a');
        }
        out.push_back(static_cast<char>(c));
    }
    return out;
}

} // namespace smufl_mapping::detail
