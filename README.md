# smufl-mapping

**smufl-mapping** is a lightweight C++ library that provides lookup tables for SMuFL glyph names, Unicode codepoints, and descriptive metadata. It covers both the standard SMuFL specification and legacy music fonts, using a metadata format originally developed by MakeMusic for Finale’s legacy fonts.

---

## Features

- Maps SMuFL glyph names to:
  - Unicode codepoints
  - Human-readable descriptions
  - Glyph source (SMuFL, Finale, etc.)
- Separated sources:
  - `glyphnames_smufl.h` for standard SMuFL metadata
  - `glyphnames_finale.h` for Finale-specific glyphs
  - `glyphnames_bravura.h` for Bravura-specific glyphs
  - legacy music font mappings
- Encapsulated via internal namespaces.
- Public lookup API via `smufl_mapping.h`
- Requires **C++17 or higher**
- MIT licensed — free for commercial and open-source use

---

## Legacy font mappings

The files in `source_json/legacy` describe mappings from legacy music-font
codepoints (as used by Finale and similar systems) to SMuFL glyphs and Unicode
codepoints.

The format stores each glyph as an array of mapping objects (so multiple
legacy codepoints per glyph remain valid JSON) and is validated against SMuFL
reference metadata as well as [`docs/legacy_mapping.schema.json`](docs/legacy_mapping.schema.json).

For a full description of the legacy mapping format, see:
[`docs/legacy_mapping_format.md`](docs/legacy_mapping_format.md)

---

## Usage

### CMake (via FetchContent)

```cmake
include(FetchContent)

FetchContent_Declare(
    smufl_mapping
    GIT_REPOSITORY https://github.com/rpatters1/smufl-mapping.git
    GIT_TAG main  # or use a version tag, branch name, or commit number
    DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)

FetchContent_MakeAvailable(smufl_mapping)

target_link_libraries(your_target PRIVATE smufl_mapping)
```

### Consuming the library requires no Python

By default the build uses the generated headers checked into `src/detail/`, so a client
needs no Python and no `FetchContent` of `w3c/smufl`. This is deliberate: **Python is a
maintainer dependency, not a client dependency.** Keeping the generated headers in the
repository is what makes that possible, so they are committed alongside the JSON they are
generated from.

To regenerate the headers instead — which requires Python 3 and fetches `w3c/smufl` — set:

```cmake
set(SMUFL_MAPPING_USE_PREGENERATED_HEADERS OFF)
```

Two consequences worth knowing when working on the project itself:

- The JSON source data, the Python tooling under `tools/`, and the Python tests are all
  only exercised when regeneration is enabled. In particular **the Python tests register
  with CTest only in that configuration**, so a default `ctest` run reports fewer tests and
  will not catch a regression in the validator or generators. CI runs both configurations;
  a local check of tooling changes should use `-DSMUFL_MAPPING_USE_PREGENERATED_HEADERS=OFF`.
- After changing anything under `source_json/`, regenerate and commit the resulting headers,
  or clients will keep seeing the previous data.

Then in C++:

```cpp
#include "smufl_mapping.h"

auto glyph = smufl_mapping::getGlyphInfo("gClef");
if (glyph) {
    std::cout << "Codepoint: " << std::hex << glyph->codepoint << "\n";
}
```

See `src/smufl_mapping.h` for a complete list of functions.

---

## VS Code setup

Starter VS Code configs are available in `.vscode_template/` for macOS, Linux, and Windows.
See `.vscode_template/README.md` for setup instructions.

---

## Generated Files

This project includes auto-generated headers derived from SMuFL metadata:

- `src/detail/glyphnames_smufl.h` — from `metadata/glyphnames.json` in the fetched `w3c/smufl` repo (official glyph definitions)
- `src/detail/glyphnames_finale.h` — from `glyphnamesFinale.json` (list of optional-range glyphs shared by all MakeMusic SMuFL fonts)
- `src/detail/glyphnames_bravura.h` — from `glyphnamesBravura.json` (optional-range glyphs, copied from Bravura's own metadata)
- `src/detail/legacy/...` — legacy font mappings from legacy mapping files in `source_json/legacy`

Python scripts in `tools/` regenerate these files automatically as needed.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

The MIT license covers this project's own work. Some of the data it builds on
originates with MakeMusic, Inc., and [NOTICE.md](NOTICE.md) sets out exactly
which data that is and where it came from. Each legacy mapping file also records
its own origin in `fontMetadata.provenance`.

---

## Credits

- SMuFL data from the `w3c/smufl` repository and published spec: [https://w3c.github.io/smufl](https://w3c.github.io/smufl)
- Legacy font mapping data and Finale glyph metadata originating with MakeMusic, Inc.,
  used for interoperability — see [NOTICE.md](NOTICE.md).
- Bravura optional-glyph metadata © 2019 Steinberg Media Technologies GmbH, under the
  SIL Open Font License 1.1 — see [NOTICE.md](NOTICE.md).
