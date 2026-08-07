"""Font-name key normalization shared by the generators and the validator.

This mirrors `normalizeFontKey()` in `src/detail/font_key.h` byte for byte. Two
implementations are unavoidable: the C++ normalizes arbitrary caller input at
runtime, while Python normalizes at generation time to emit the sorted table
keys, and neither side can call the other in a build that must work on a bare
Python. `tests/data/font_key_vectors.json` is the shared contract that keeps
them honest; both languages are tested against it.

The rule is deliberately narrow — fold ASCII case, drop ASCII whitespace, leave
everything else alone:

* Only the six ASCII whitespace characters are removed. Python's `str.split()`
  would additionally swallow U+001C-U+001F, U+0085, U+00A0 and U+3000, none of
  which the C++ sees as whitespace, so using it here would let the generator
  mint keys no runtime input could ever reach.
* Only A-Z are lowercased. Python's `str.lower()` is Unicode-aware and would
  case-fold accented letters that the byte-oriented C++ leaves untouched.

Non-ASCII bytes pass through unchanged on both sides, so a UTF-8 string
normalizes identically whether it is walked as characters (Python) or as bytes
(C++): every byte of a multi-byte sequence is >= 0x80 and so is never matched by
either rule above.
"""

from __future__ import annotations

# Space plus U+0009-U+000D: tab, newline, vertical tab, form feed, carriage
# return. This is exactly what std::isspace() reports in the "C" locale.
ASCII_WHITESPACE = frozenset(" \t\n\v\f\r")


def normalize_font_key(name: str) -> str:
    """Normalize a font name for lookup: fold ASCII case, drop ASCII whitespace."""
    out = []
    for ch in name:
        if ch in ASCII_WHITESPACE:
            continue
        out.append(chr(ord(ch) + 32) if "A" <= ch <= "Z" else ch)
    return "".join(out)
