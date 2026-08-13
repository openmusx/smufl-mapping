## Legacy font mapping JSON format

Each file in `source_json/legacy` defines a mapping from **legacy music-font codepoints** (as used by Finale and other pre-SMuFL systems) to **SMuFL glyphs** and Unicode codepoints. The file is a JSON object with two members: `fontMetadata`, describing the legacy font as a whole, and `glyphs`, whose keys are SMuFL glyph names and whose values describe how each glyph appears in the legacy font being mapped.

The authoritative schema lives in [`docs/legacy_mapping.schema.json`](legacy_mapping.schema.json). The summary below mirrors that schema.

`tools/validate_legacy_mappings.py` executes that schema when the `jsonschema` module is available, so it is a live check rather than prose that can drift. The module is deliberately **not** a build dependency — regenerating headers must work on a bare Python — so when it is missing the script says so and falls back to its hand-written checks, which cover the same rules. Install `jsonschema` when editing either the schema or the validator, so that the two are verified against each other.

### Top-level structure

- The file is a JSON object with exactly two members, both required: `fontMetadata` and `glyphs`.
- Within `glyphs`:
  - **Keys** are SMuFL glyph names (strings). Leading and trailing whitespace is ignored.
  - **Values** are arrays of entry objects. Even if only one mapping exists, it must be wrapped in an array. This keeps the files valid JSON while preserving multiple legacy mappings per glyph. Each entry in that array may itself list multiple legacy codepoints, which means you can express “1 glyph ↔ N legacy slots” in two ways:
    1. One entry with a multiple `legacyCodepoints` elements.
    2. Multiple entry objects that differ only by the legacy element(s).

    Both approaches expand to the same generated output.

Keeping font-level facts in their own object is what makes them checkable: when every top-level key was a glyph name, a misspelled metadata key was indistinguishable from a glyph name and could never be rejected. `fontMetadata` is validated with `additionalProperties: false`, so a typo is a hard error.

### `fontMetadata` fields

| Field name           | Type            | Required | Description |
|----------------------|-----------------|----------|-------------|
| `fontType`           | string          | yes      | Either `"engraving"` (placed in the score as notation) or `"text"` (set inline with running text, such as chord symbols, metronome marks, and expression text). |
| `fontStyle`          | string          | yes      | Either `"engraved"` (imitates plate engraving) or `"handwritten"` (imitates manuscript). Independent of `fontType`. |
| `smuflSuccessorFont` | string or null  | yes      | The SMuFL font that supersedes this legacy font. `null` when none has been established. |
| `successorNotes`     | string          | no       | Why `smuflSuccessorFont` holds the value it does. Expected whenever the value is `null` or the choice is not obvious. |
| `staffSpacesPerEm`   | number or null  | yes      | How many staff spaces one em spans in this font. `null` means the font opts out of size mapping. |
| `sizeNotes`          | string          | no       | Why `staffSpacesPerEm` holds the value it does. Expected whenever the value is `null` or was inferred rather than measured. |
| `provenance`         | string          | yes      | Either `"finale-sourced"` or `"independent"`. Where this file's glyph table originates. |
| `provenanceNotes`    | string          | no       | What the mapping was derived from and what has changed since. Expected on every file; the validator warns when it is absent. |

#### `fontType` and `fontStyle` are orthogonal

`fontType` is the font's **role** — where it goes. `fontStyle` is its **appearance**. Neither can be derived from the other: seven of the mapped fonts are handwritten *and* text-role, including `JazzText`, `Broadway Copyist Text` and `JazzCord`. A single combined enum would force each of those to drop one fact, so they are kept as separate fields.

`fontStyle` is recorded from knowledge of the font, not measured. Two geometric metrics were tried and neither separates the two classes reliably: outline point count fails outright (Jazz is a clean handwritten design with fewer points than Maestro), and deviation from 180° rotational symmetry separates the Jazz family clearly but leaves Broadway Copyist — neat handwriting — overlapping Chaconne and Kousaku. The distinction is an editorial judgement about appearance, and no geometric threshold captures it.

#### `provenance`

Some of these mapping files were seeded from the legacy-font conversion data that Finale 27 distributed; others were compiled for this project because Finale carried no such data for the font. `provenance` records which, so the distinction is a checkable property of each file rather than institutional memory. [`NOTICE.md`](../NOTICE.md) explains why the project tracks it.

The value is deliberately binary. Grading *how much* revision followed would put a number in the data that goes stale on the next edit, and the interesting question — did this table originate with MakeMusic's data or not — has only two answers. The degree of revision goes in `provenanceNotes` as prose, where it can be stated with the hedging it deserves.

`provenance` is required, unlike `successorNotes` and `sizeNotes`. There is no "not yet established" state for it: a file either came from Finale's conversion data or it did not, and a new mapping file whose origin nobody recorded is precisely what the field exists to prevent.

**The generator does not read it.** Provenance is a fact about how a source file came to exist, not about the font, so it stays in `source_json/` and never reaches a generated header or the API.

#### Fonts with no glyph mappings

A file may carry `fontMetadata` with an empty `glyphs` object. That records a font whose successor and sizing are known while its codepoint mappings are not available — `Sonata` and `Ash Music` are the current examples. Font-level lookup through `getLegacyFontInfo()` succeeds for these, while every glyph lookup correctly finds nothing.

The generator emits no array for such a font and pairs it with a null table, because a zero-length array is a compiler extension that the project's `-Wpedantic -Werror` build rejects.

#### `smuflSuccessorFont`

A client replacing a legacy font with a modern one needs to know which SMuFL face to name. `smuflSuccessorFont` records it, so that knowledge lives with the mapping rather than being duplicated in each client.

A `"text"` font names a SMuFL **text** face where one exists, so a substituted glyph keeps text metrics rather than staff metrics — `JazzText` names `"Finale Jazz Text"`, not `"Finale Jazz"`. Where no text face exists the music face is named instead, which `successorNotes` records.

Note that a successor is not the same claim as shared design. Most values were established by measurement — comparing glyph aspect ratios, which are scale-invariant and so identify which face inherited a legacy font's outlines regardless of em scale. But a font may name a successor purely as a deliberate substitution: `Pmusic` derives from Sonata, which has no SMuFL migration path, so it names `"Finale Maestro"` as a best fit while matching no SMuFL face by design. `successorNotes` distinguishes the two cases.

`null` means no successor has been established; a client should fall back to its own default rather than guess. In the C++ API this surfaces as an empty `smuflSuccessorFont`:

```cpp
if (auto info = smufl_mapping::getLegacyFontInfo(fontName)) {
    if (!info->smuflSuccessorFont.empty()) {
        // name info->smuflSuccessorFont as the substituted font
    }
}
```

#### `staffSpacesPerEm` and font size

A conforming SMuFL font is designed so that **one em spans exactly four staff spaces**. That is what makes a point size portable between two SMuFL fonts. A legacy font makes no such promise, so its point size may describe only its own design and would mis-scale a substituted SMuFL glyph.

`staffSpacesPerEm` records what the legacy font actually does, letting a client convert:

```
smuflPointSize = legacyPointSize * (4.0 / staffSpacesPerEm)
```

The C++ API exposes this through `getLegacyFontInfo()`, which returns a `LegacyFontInfo` whose `smuflSizeRatio()` performs the division:

```cpp
if (auto info = smufl_mapping::getLegacyFontInfo(fontName)) {
    if (auto ratio = info->smuflSizeRatio()) {
        smuflPointSize = legacyPointSize * (*ratio);
    }
    // else: this font opts out; do not emit a size.
}
```

`staffSpacesPerEm` is deliberately stored rather than the ratio, because it is a property of the legacy font alone: it can be re-measured from the font file without presupposing which SMuFL font gets substituted.

**Opting out.** A font sets `staffSpacesPerEm` to `null` when its point size has no staff-relative meaning, or when it cannot be established. The key is always present, so an opt-out is never confused with an oversight. Clients must not derive a size for glyphs mapped from such a font. Note the distinction in the API: an unknown font returns `std::nullopt` from `getLegacyFontInfo()`, whereas a known font that opts out returns an engaged `LegacyFontInfo` whose `staffSpacesPerEm` is `std::nullopt`.

**Measuring the value.** `tools/measure_legacy_font_sizes.py` derives these values from installed font files. It is a maintainer-only utility and is deliberately not wired into the build, since it needs fontTools and (for a few Type 1 fonts) macOS CoreText. It uses two independent estimates:

1. **Successor comparison.** Where a legacy font's outlines were reused into a SMuFL font at an identical em scale, the per-glyph size ratio lands on *exactly* 4.0. The size of that spike is the confidence signal; a redrawn design produces a broad scatter instead.
2. **`staff5Lines` anchor.** Independent of any successor font: a five-line staff glyph is four staff spaces tall plus one staff-line thickness, so `4.128 / legacyHeightInEm` estimates the value directly.

Run `--check` to confirm the committed values are still corroborated by measurement.

### `glyphs` entry object fields

Each entry object may contain the following fields:

| Field name         | Type            | Required | Description |
|--------------------|-----------------|----------|-------------|
| `legacyCodepoints` | array of string | yes      | One or more legacy font codepoints (decimal or C-style hex). Values must be unique within the array. |
| `codepoint`        | string          | yes*     | The Unicode codepoint of the corresponding SMuFL glyph, written as `"U+XXXX"`. Special handling applies for `"U+FFFD"` (see below). |
| `description`      | string          | no       | A human-readable description of the glyph. Defaults to the empty string if omitted. |
| `nameIsMakeMusic`  | boolean         | no       | Kept for historical accuracy; surfaced but unused by the generator. |
| `smuflFontName`    | string          | no       | Name of the SMuFL font that supplied an optional glyph (e.g., `"Finale Broadway"`, `"Bravura"`). Any value other than `"Bravura"` is treated as Finale metadata. |
| `xOffset`,`yOffset`| integer string  | no       | Finale-specific positional values, preserved but **not** consumed. See below. |
| `alternate`        | boolean         | no       | Set to `true` when the entry intentionally differs from the canonical SMuFL mapping. Absent (or `false`) entries are considered canonical and are preferred during lookups. |
| `notes`            | string          | no       | Free-form annotations for future maintainers. |

\* `codepoint` is required unless it is explicitly set to `"U+FFFD"` and can be resolved from reference data.

#### `xOffset` and `yOffset` are preserved, not applied

These are Finale-specific values carried over unchanged from the original MakeMusic mapping data. They have no general applicability *yet*, so the generator does not read them and `LegacyGlyphInfo` has no field for them. **Nothing in the API exposes them.**

They are nonetheless retained deliberately. If this format is ever put forward as a standard schema for legacy font mapping, positional data of this kind has already been asked for, and it is not reconstructible once dropped: the values are not derivable from the fonts, so discarding them would be a one-way door. Carrying two unread fields is the cheaper mistake.

The unit is thousandths of an em. In most entries the value equals the legacy glyph's own bounding-box origin — Maestro's `caesura` records `xOffset` `14` against a glyph whose origin sits at 0.014 em, and its `brassMuteClosed` records `yOffset` `-148` against an origin of −0.148 em. A handful of entries do not follow that pattern, so the values should be treated as historical record rather than a formula.

192 entries across six files carry them: Broadway Copyist, Engraver Font Set, Jazz, Maestro, Maestro Wide, and Petrucci.

### Handling of `U+FFFD`

If `codepoint` is `"U+FFFD"`, the script attempts to resolve the actual Unicode codepoint by looking up the glyph name in `glyphnamesFinale.json`. This works around how the original Finale mappings were coded. Future contributions should supply explicit Unicode codepoints rather than relying on this fallback.

If resolution fails, a warning is emitted and the entry is generated with a **`std::nullopt` codepoint**, which is how `LegacyGlyphInfo::codepoint` spells "unspecified". The entry itself is kept, because the glyph *name* is still known and useful even when the codepoint is not. Callers must therefore check the optional before dereferencing it:

```cpp
if (const auto* info = getLegacyGlyphInfo(fontName, legacyCodepoint)) {
    if (info->codepoint) {
        // a SMuFL codepoint is known
    }
    // info->name is valid either way
}
```

Every `U+FFFD` entry in the current corpus resolves, so no generated table holds an unspecified codepoint today; the behavior matters for future contributions.

### Optional-range glyphs (U+F400–U+F8FF)

Unicode codepoints in the private-use optional SMuFL range (`U+F400`–`U+F8FF`) are validated against reference glyph lists:

- If `smuflFontName` is `"Bravura"`, the glyph must exist in `glyphnamesBravura.json`.
- Otherwise, it must exist in `glyphnamesFinale.json`.

Optional-range entries whose glyph names are not found in the appropriate reference list are omitted.

Additional SMuFL font sources may be supported in the future, and contributions that extend the set of optional glyph sources are welcome.

### Glyph source classification

Each processed entry is tagged with a source indicating where the Unicode codepoint originates:

- `SmuflGlyphSource::Smufl`  
  For codepoints outside the optional private-use range.
- `SmuflGlyphSource::Finale`  
  For optional-range glyphs resolved via Finale metadata.
- `SmuflGlyphSource::Bravura`  
  For optional-range glyphs resolved via Bravura metadata.

### Sample mapping entry

```json
{
    "fontMetadata": {
        "fontType": "engraving",
        "staffSpacesPerEm": 4.0
    },
    "glyphs": {
        "enclosureClosed": [
            {
                "nameIsMakeMusic": true,
                "codepoint": "U+F74A",
                "legacyCodepoints": ["94"],
                "description": "",
                "smuflFontName": "Finale Broadway"
            }
        ],
        "gClef": [
            {
                "codepoint": "U+E050",
                "legacyCodepoints": ["38"],
                "description": ""
            }
        ]
    }
}
```

A font that opts out of size mapping records why:

```json
{
    "fontMetadata": {
        "fontType": "text",
        "staffSpacesPerEm": null,
        "sizeNotes": "Measurements scatter with no coherent scale, so no staff-relative size can be established."
    },
    "glyphs": { }
}
```

### Known inconsistencies

The legacy metadata reflects Finale’s final release verbatim, which means some
slots conflict with the canonical SMuFL definitions. One notable case is
`brassMuteClosed`: several fonts map legacy codepoint `246` to the *glissando*
glyph `U+E585` (Finale labeled the slot as an alternate “+” symbol). That is
almost certainly wrong, but until there is a real-world need to rewrite those
files the project preserves the historical data and relies on lookup routines
to prefer the canonical slot `43` instead.
