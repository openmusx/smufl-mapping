#!/usr/bin/env python3
"""Measure the `staffSpacesPerEm` value for legacy fonts.

This is a *maintainer-only* utility. It is deliberately NOT wired into CMake: it
needs fontTools and (on macOS) CoreText, neither of which is a build dependency
of smufl_mapping. Its purpose is to let the `fontMetadata.staffSpacesPerEm`
values committed in source_json/legacy/*.json be re-derived and re-verified.

Background
----------
A conforming SMuFL font is designed so that one em spans exactly four staff
spaces. Legacy (pre-SMuFL) fonts make no such promise, so a consumer that
substitutes a SMuFL glyph for a legacy one cannot assume the original point size
carries over. `staffSpacesPerEm` records, per legacy font, how many staff spaces
one em actually spans, so a client can compute:

    smuflPointSize = legacyPointSize * (4.0 / staffSpacesPerEm)

Method
------
Two independent estimates are computed and reported side by side.

1. Successor comparison. MakeMusic derived the Finale SMuFL fonts from these
   legacy fonts by reusing outlines at an identical em scale. So for every glyph
   the mapping file pairs up, we compare the legacy glyph's bounding box (in em)
   against the same glyph in the successor SMuFL font (in staff spaces). Where
   the outline really was reused, the ratio lands on *exactly* 4.0, which shows
   up as a large spike at 4.0 rather than a merely-close median. The size of
   that spike is the confidence signal; a design that was redrawn produces a
   broad scatter instead.

2. staff5Lines anchor. Independent of any successor font: a five-line staff
   glyph is four staff spaces tall plus one staff-line thickness. Using
   Bravura's value of 4.128 spaces, `4.128 / legacyHeightInEm` estimates
   spaces-per-em directly. Only some fonts map staff5Lines, but where both
   methods apply they agree closely, which is what validates method 1.

Both methods need a SMuFL codepoint for each legacy glyph, so U+FFFD entries are
resolved through glyphnamesFinale.json exactly as the generator does. Skipping
them instead would silently exclude 199 entries, and would leave a font like
Engraver Time -- whose every entry is U+FFFD *and* alternate -- with nothing to
measure at all.

Usage
-----
    python3 tools/measure_legacy_font_sizes.py
    python3 tools/measure_legacy_font_sizes.py --font Maestro --verbose
    python3 tools/measure_legacy_font_sizes.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = BASE_DIR / "source_json" / "legacy"

# A conforming SMuFL font spans four staff spaces per em, by definition.
SMUFL_STAFF_SPACES_PER_EM = 4.0

# Bravura's staff5Lines is four staff spaces plus one staff-line thickness.
STAFF_5_LINES_SPACES = 4.128

# Directories searched for installed fonts, in order.
FONT_DIRS = [
    Path("/Library/Fonts"),
    Path.home() / "Library" / "Fonts",
    Path("/System/Library/Fonts"),
    # MuseScore bundles several SMuFL faces that are not installed system-wide,
    # including the copy of Emmentaler it ships under the family name MScore.
    Path.home() / "MuseScore" / "fonts" / "mscore",
    Path.home() / "MuseScore" / "fonts" / "gootville",
    Path.home() / "MuseScore" / "fonts" / "musejazz",
]

# Legacy font (JSON stem) -> candidate filenames on disk.
LEGACY_FONT_FILES: Dict[str, List[str]] = {
    "Broadway Copyist": ["BroadwayCopyist_TT.suit"],
    "Broadway Copyist Perc": ["BroadwayCopyistPerc_TT.suit"],
    "Broadway Copyist Text": ["BroadwayCopyistText_TT.suit"],
    "Broadway Copyist Text Ext": ["BroadwayCopyistTextExt_TT.suit"],
    "Chaconne": ["Chaconne.suit", "Chaconne.ttf", "Chaconne.otf"],
    "Crescendo": ["Cresc", "Crescendo.suit"],
    "Engraver Font Extras": ["EngraverFontExtras.suit"],
    "Engraver Font Set": ["EngraverFontSet.suit"],
    "Engraver Text H": ["EngraverTextH.suit"],
    "Engraver Text NCS": ["EngraverTextNCS.suit"],
    "Engraver Text T": ["EngraverTextT.suit"],
    "Engraver Time": ["EngraverTime.suit"],
    "Finale AlphaNotes": ["Finale AlphaNotes"],
    "Finale Copyist Text": ["Finale Copyist Text.ttf"],
    "Finale Copyist Text Ext": ["Finale Copyist Text Ext.ttf"],
    "Finale Mallets": ["Finale Mallets"],
    "Finale Numerics": ["Finale Numerics.ttf"],
    "Finale Percussion": ["Finale Percussion"],
    "GraceNotes": ["GraceNot", "GraceNotes.suit"],
    "Jazz": ["Jazz.suit"],
    "JazzCord": ["JazzCord.suit"],
    "JazzPerc": ["JazzPerc.suit"],
    "JazzText": ["JazzText.suit"],
    "JazzText Extended": ["JazzText Extended.suit"],
    "Kousaku": ["Kousaku.suit", "Kousaku.ttf", "Kousaku.otf"],
    "Kousaku Percussion": [
        "Kousaku Percussion.suit",
        "Kousaku Percussion.ttf",
        "KousakuPercussion.ttf",
    ],
    "Maestro": ["Maestro.suit"],
    "Maestro Percussion": ["Maestro Percussion.suit"],
    "Maestro Wide": ["Maestro Wide.suit"],
    "MaestroTimes": ["MaestroTimes.ttf"],
    "Patmm": ["Patmm.otf", "Patmm.ttf"],
    "Petrucci": ["Petrucci.suit"],
    "Pmusic": ["Pmusic.otf", "Pmusic.ttf"],
    "Rentaro": ["Rentaro.suit", "Rentaro.ttf", "Rentaro.otf"],
    "Tamburo": ["Tamburo.suit"],
}

# CoreText family name, used only for fonts fontTools cannot open (Type 1 LWFN).
LEGACY_CORETEXT_NAMES: Dict[str, str] = {
    "Crescendo": "Crescendo",
    "GraceNotes": "GraceNotes",
}

# Legacy font -> the SMuFL font MakeMusic derived from it (method 1 reference).
SUCCESSOR_FONTS: Dict[str, str] = {
    # Chaconne's successor is the SMuFL font "Chaconne Ex". It is not installed
    # here, so no successor comparison is possible and the value rests on the
    # staff5Lines anchor instead. Naming it anyway keeps the record accurate:
    # substituting a different font would report a comparison against a face
    # that never inherited Chaconne's outlines.
    "Chaconne": "ChaconneEx",
    "Kousaku": "FinaleLegacy",
    "Kousaku Percussion": "FinaleLegacy",
    "Rentaro": "FinaleMaestro",
    "Broadway Copyist": "FinaleBroadway",
    "Broadway Copyist Perc": "FinaleBroadway",
    "Broadway Copyist Text": "FinaleBroadway",
    "Broadway Copyist Text Ext": "FinaleBroadway",
    "Engraver Font Extras": "FinaleEngraver",
    "Engraver Font Set": "FinaleEngraver",
    "Engraver Text H": "FinaleEngraver",
    "Engraver Text NCS": "FinaleEngraver",
    "Engraver Text T": "FinaleEngraver",
    "Engraver Time": "FinaleEngraver",
    "Finale AlphaNotes": "FinaleMaestro",
    # The Copyist text faces were reused into the SMuFL *text* font, not the
    # music font; see the note on text fonts below.
    "Finale Copyist Text": "FinaleBroadwayText",
    "Finale Copyist Text Ext": "FinaleBroadwayText",
    "Finale Mallets": "FinaleMaestro",
    "Finale Numerics": "FinaleMaestro",
    "Finale Percussion": "FinaleMaestro",
    "Jazz": "FinaleJazz",
    "JazzCord": "FinaleJazz",
    "JazzPerc": "FinaleJazz",
    "JazzText": "FinaleJazz",
    "JazzText Extended": "FinaleJazz",
    "Maestro": "FinaleMaestro",
    "Maestro Percussion": "FinaleMaestro",
    "Maestro Wide": "FinaleMaestro",
    "MaestroTimes": "FinaleMaestroText",
    "Patmm": "FinaleMaestro",
    "Petrucci": "FinaleLegacy",
    "Pmusic": "FinaleMaestro",
    "Tamburo": "FinaleLegacy",
    "Crescendo": "FinaleMaestro",
    "GraceNotes": "FinaleMaestro",
}

REFERENCE_FONT_FILES: Dict[str, str] = {
    "FinaleMaestro": "FinaleMaestro.otf",
    "FinaleLegacy": "FinaleLegacy.otf",
    "FinaleJazz": "FinaleJazz.otf",
    "FinaleEngraver": "FinaleEngraver.otf",
    "FinaleBroadway": "FinaleBroadway.otf",
    "FinaleBroadwayText": "FinaleBroadwayText.otf",
    "FinaleMaestroText": "FinaleMaestroText-Regular.otf",
    "ChaconneEx": "ChaconneEx.otf",
    "Bravura": "Bravura.otf",
}

# A SMuFL *music* font spans four staff spaces per em by definition, but a SMuFL
# *text* font does not: it is scaled for running text. Measured by comparing each
# text font against its music counterpart over all shared U+E000..U+F7FF glyphs,
# BravuraText's dominant mode is 1.250 (so 5.0 spaces per em), while MakeMusic's
# Finale text faces sit on the music em scale at 1.000. A reference font must
# therefore declare its own scale rather than assume 4.0.
REFERENCE_STAFF_SPACES_PER_EM: Dict[str, float] = {
    "FinaleBroadwayText": 4.0,
    "FinaleMaestroText": 4.0,
}

# Bounding boxes smaller than this (in em, or in staff spaces) are dominated by
# rounding and would blow up the ratio, so they are skipped.
MIN_EXTENT = 0.05

# A ratio counts as an exact outline reuse if it is within this of 4.0.
EXACT_TOLERANCE = 0.004


def find_font(candidates: Iterable[str]) -> Optional[Path]:
    for name in candidates:
        for directory in FONT_DIRS:
            path = directory / name
            if path.exists():
                return path
    return None


class FontMetrics:
    """Glyph bounding boxes in em units, keyed by codepoint."""

    def __init__(self, label: str):
        self.label = label

    def bbox_em(self, codepoint: int) -> Optional[Tuple[float, float]]:
        """Return (width, height) in em units, or None if the glyph is absent."""
        raise NotImplementedError


class SfntMetrics(FontMetrics):
    """Reads any sfnt-based font, including Mac resource-fork suitcases."""

    def __init__(self, label: str, path: Path, prefer_mac_roman: bool):
        super().__init__(label)
        from fontTools.ttLib import TTFont
        from fontTools.ttLib.macUtils import getSFNTResIndices

        try:
            font = TTFont(str(path), fontNumber=0, lazy=True)
        except Exception:
            # Most legacy Finale fonts are suitcases whose data fork is empty;
            # the sfnt lives in the resource fork.
            indices = getSFNTResIndices(str(path))
            if not indices:
                raise
            font = TTFont(str(path), res_name_or_index=indices[0], lazy=True)

        self._font = font
        self._glyph_set = font.getGlyphSet()
        self._upem = font["head"].unitsPerEm

        # Legacy codepoints in the mapping files are usually byte values matching
        # the fonts' (1, 0) Mac Roman format-0 subtable, so getBestCmap() alone
        # would silently mismatch. But some files (e.g. Patmm) record the high
        # Mac Roman positions by their Unicode equivalent instead -- 8224 for
        # 0xA0 'dagger', 8706 for 0xB6 'partialdiff', and so on -- so both
        # subtables are kept and chosen per codepoint.
        self._unicode_cmap = font.getBestCmap()
        self._mac_cmap = None
        if prefer_mac_roman:
            for table in font["cmap"].tables:
                if (table.platformID, table.platEncID) == (1, 0):
                    self._mac_cmap = table.cmap
                    break

    def _glyph_name(self, codepoint: int) -> Optional[str]:
        if self._mac_cmap is not None and codepoint <= 0xFF:
            name = self._mac_cmap.get(codepoint)
            if name:
                return name
        return self._unicode_cmap.get(codepoint)

    @property
    def units_per_em(self) -> int:
        return self._upem

    def bbox_em(self, codepoint: int) -> Optional[Tuple[float, float]]:
        from fontTools.pens.boundsPen import BoundsPen

        glyph_name = self._glyph_name(codepoint)
        if not glyph_name:
            return None
        pen = BoundsPen(self._glyph_set)
        try:
            self._glyph_set[glyph_name].draw(pen)
        except Exception:
            return None
        if not pen.bounds:
            return None
        x_min, y_min, x_max, y_max = pen.bounds
        return ((x_max - x_min) / self._upem, (y_max - y_min) / self._upem)


CORETEXT_SWIFT = r"""
import CoreText
import Foundation

let args = CommandLine.arguments
let familyName = args[1]
let font = CTFontCreateWithName(familyName as CFString, 1000.0, nil)
let actualName = CTFontCopyFullName(font) as String
print("FONT\t\(actualName)")
for arg in args.dropFirst(2) {
    guard let code = UInt32(arg), code <= 0xFF else { continue }
    let data = Data([UInt8(code)])
    guard let text = String(data: data, encoding: .macOSRoman) else {
        print("\(arg)\tNONE"); continue
    }
    let chars = Array(text.utf16)
    var glyphs = [CGGlyph](repeating: 0, count: chars.count)
    let ok = CTFontGetGlyphsForCharacters(font, chars, &glyphs, chars.count)
    if !ok || glyphs.isEmpty || glyphs[0] == 0 {
        print("\(arg)\tNONE"); continue
    }
    var glyph = [glyphs[0]]
    let rect = CTFontGetBoundingRectsForGlyphs(font, .default, &glyph, nil, 1)
    print("\(arg)\t\(rect.width / 1000.0)\t\(rect.height / 1000.0)")
}
"""


class CoreTextMetrics(FontMetrics):
    """Fallback for fonts fontTools cannot open, e.g. Type 1 LWFN suitcases.

    CoreText resolves fonts by name rather than by path and will silently
    substitute a default face for a name it does not know, so the resolved full
    name is checked against the request before any measurement is trusted.
    """

    def __init__(self, label: str, family_name: str, codepoints: Iterable[int]):
        super().__init__(label)
        if sys.platform != "darwin":
            raise RuntimeError("CoreText fallback is only available on macOS")
        swift = shutil.which("swift")
        if not swift:
            raise RuntimeError("swift not found; cannot use the CoreText fallback")

        wanted = sorted({cp for cp in codepoints if 0 <= cp <= 0xFF})
        with tempfile.NamedTemporaryFile("w", suffix=".swift", delete=False) as handle:
            handle.write(CORETEXT_SWIFT)
            script = handle.name
        try:
            result = subprocess.run(
                [swift, script, family_name, *[str(cp) for cp in wanted]],
                capture_output=True,
                text=True,
                timeout=300,
            )
        finally:
            Path(script).unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(f"swift failed for '{family_name}': {result.stderr.strip()[:200]}")

        self._boxes: Dict[int, Tuple[float, float]] = {}
        resolved = None
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if parts[0] == "FONT":
                resolved = parts[1]
                continue
            if len(parts) != 3 or parts[1] == "NONE":
                continue
            self._boxes[int(parts[0])] = (float(parts[1]), float(parts[2]))

        normalized = "".join(family_name.lower().split())
        if not resolved or normalized not in "".join(resolved.lower().split()):
            raise RuntimeError(
                f"CoreText resolved '{family_name}' to '{resolved}'; font is not installed"
            )

    def bbox_em(self, codepoint: int) -> Optional[Tuple[float, float]]:
        return self._boxes.get(codepoint)


class ReferenceFont:
    """A SMuFL reference font; reports bounding boxes in staff spaces."""

    def __init__(self, name: str, path: Path):
        self.name = name
        self._metrics = SfntMetrics(name, path, prefer_mac_roman=False)
        self._spaces_per_em = REFERENCE_STAFF_SPACES_PER_EM.get(
            name, SMUFL_STAFF_SPACES_PER_EM
        )

    def bbox_spaces(self, codepoint: int) -> Optional[Tuple[float, float]]:
        box = self._metrics.bbox_em(codepoint)
        if box is None:
            return None
        return (box[0] * self._spaces_per_em, box[1] * self._spaces_per_em)


def load_mapping(path: Path) -> Dict[str, List[dict]]:
    """Read a legacy mapping file, accepting both the wrapper and legacy flat shape."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict) and "glyphs" in data and "fontMetadata" in data:
        return data["glyphs"]
    return data


def committed_metadata(path: Path) -> dict:
    """The fontMetadata currently recorded in a mapping file."""
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {}
    return data.get("fontMetadata") or {}


def load_finale_glyphnames() -> Dict[str, int]:
    """Glyph name -> codepoint, used to resolve U+FFFD the way the generator does."""
    path = BASE_DIR / "source_json" / "glyphnamesFinale.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        name.strip(): int(props["codepoint"][2:], 16)
        for name, props in data.items()
        if "codepoint" in props
    }


def collect_pairs(
    glyphs: Dict[str, List[dict]],
    finale_names: Optional[Dict[str, int]] = None,
    include_alternate: bool = False,
) -> List[Tuple[str, int, int]]:
    """Yield (glyphName, legacyCodepoint, smuflCodepoint) for comparable entries.

    U+FFFD defers resolution to glyphnamesFinale.json, exactly as the generator
    does, so those entries are usable once resolved rather than being dropped.

    `alternate` entries deliberately point somewhere other than the canonical
    glyph, so they are excluded by default: comparing one would measure two
    different designs against each other. Some fonts are entirely alternate
    though, and excluding them leaves nothing to measure at all, so the caller
    can opt back in.
    """
    finale_names = finale_names or {}
    pairs = []
    for glyph_name, entries in glyphs.items():
        for entry in entries:
            if entry.get("alternate") and not include_alternate:
                continue
            codepoint = entry.get("codepoint")
            if not codepoint:
                continue
            if codepoint == "U+FFFD":
                smufl_cp = finale_names.get(glyph_name.strip())
                if smufl_cp is None:
                    continue
            else:
                smufl_cp = int(codepoint[2:], 16)
            for raw in entry.get("legacyCodepoints", []):
                pairs.append((glyph_name, int(raw, 0), smufl_cp))
    return pairs


def compare_against(
    metrics: FontMetrics,
    reference: ReferenceFont,
    pairs: List[Tuple[str, int, int]],
) -> List[Tuple[float, str]]:
    """Ratios of reference-size-in-spaces to legacy-size-in-em, one per dimension."""
    ratios: List[Tuple[float, str]] = []
    for glyph_name, legacy_cp, smufl_cp in pairs:
        legacy_box = metrics.bbox_em(legacy_cp)
        ref_box = reference.bbox_spaces(smufl_cp)
        if legacy_box is None or ref_box is None:
            continue
        for legacy_extent, ref_extent in zip(legacy_box, ref_box):
            if legacy_extent > MIN_EXTENT and ref_extent > MIN_EXTENT:
                ratios.append((ref_extent / legacy_extent, glyph_name))
    return ratios


def staff_anchor(metrics: FontMetrics, glyphs: Dict[str, List[dict]]) -> Optional[float]:
    """Estimate spaces-per-em from staff5Lines alone, with no successor font."""
    for entry in glyphs.get("staff5Lines", []):
        if entry.get("alternate"):
            continue
        for raw in entry.get("legacyCodepoints", []):
            box = metrics.bbox_em(int(raw, 0))
            if box and box[1] > MIN_EXTENT:
                return STAFF_5_LINES_SPACES / box[1]
    return None


def open_legacy_font(font_name: str, pairs: List[Tuple[str, int, int]]) -> FontMetrics:
    path = find_font(LEGACY_FONT_FILES.get(font_name, []))
    if path is not None:
        try:
            return SfntMetrics(font_name, path, prefer_mac_roman=True)
        except Exception:
            pass  # Not an sfnt (Type 1 LWFN); fall through to CoreText.
    family = LEGACY_CORETEXT_NAMES.get(font_name)
    if family:
        return CoreTextMetrics(font_name, family, [legacy for _, legacy, _ in pairs])
    if path is None:
        raise FileNotFoundError(f"font not installed")
    raise RuntimeError("font is not an sfnt and has no CoreText fallback configured")


def analyze(
    font_name: str,
    references: Dict[str, ReferenceFont],
    verbose: bool,
    finale_names: Optional[Dict[str, int]] = None,
) -> dict:
    glyphs = load_mapping(SOURCE_DIR / f"{font_name}.json")
    pairs = collect_pairs(glyphs, finale_names)

    result = {
        "font": font_name,
        "status": "ok",
        "successor": SUCCESSOR_FONTS.get(font_name),
    }

    # A font whose every entry is marked alternate would otherwise be
    # unmeasurable; fall back to those entries rather than reporting nothing.
    if not pairs:
        pairs = collect_pairs(glyphs, finale_names, include_alternate=True)
        if pairs:
            result["alternate_entries_only"] = True

    try:
        metrics = open_legacy_font(font_name, pairs)
    except Exception as exc:
        result["status"] = f"unavailable: {exc}"
        return result

    successor_name = SUCCESSOR_FONTS.get(font_name)
    ratios: List[Tuple[float, str]] = []
    if successor_name and successor_name not in references:
        # Distinguish "the successor font is not installed" from "the successor
        # is installed but shares no comparable glyphs"; both would otherwise
        # show as zero samples.
        result["successor_available"] = False
    elif successor_name:
        ratios = compare_against(metrics, references[successor_name], pairs)

    values = sorted(r for r, _ in ratios)
    result["samples"] = len(values)
    if values:
        exact = sum(1 for v in values if abs(v - SMUFL_STAFF_SPACES_PER_EM) < EXACT_TOLERANCE)
        result["median"] = round(statistics.median(values), 4)
        result["exact"] = exact
        result["exact_fraction"] = round(exact / len(values), 4)
    result["staff5Lines"] = (
        round(anchor, 4) if (anchor := staff_anchor(metrics, glyphs)) else None
    )

    if verbose and ratios:
        print(f"\n  {font_name}: per-glyph ratios vs {successor_name}")
        for ratio, glyph_name in sorted(ratios)[:5]:
            print(f"    {glyph_name:<34} {ratio:.4f}")
        print("    ...")
        for ratio, glyph_name in sorted(ratios)[-5:]:
            print(f"    {glyph_name:<34} {ratio:.4f}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--font", action="append", help="Measure only this font (repeatable).")
    parser.add_argument("--json", type=Path, help="Write the full results to this file.")
    parser.add_argument("--verbose", action="store_true", help="Show per-glyph ratios.")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare measurements against the committed staffSpacesPerEm and "
        "exit nonzero on disagreement. Fonts that are not installed are skipped.",
    )
    args = parser.parse_args()

    try:
        import fontTools  # noqa: F401
    except ImportError:
        print("fontTools is required: pip install fonttools", file=sys.stderr)
        return 1

    references: Dict[str, ReferenceFont] = {}
    for name, filename in REFERENCE_FONT_FILES.items():
        path = find_font([filename])
        if path:
            references[name] = ReferenceFont(name, path)
    if "Bravura" not in references:
        print("Warning: Bravura.otf not found; anchor cross-check is unavailable.", file=sys.stderr)

    finale_names = load_finale_glyphnames()
    font_names = args.font or sorted(p.stem for p in SOURCE_DIR.glob("*.json"))

    print(f"{'legacy font':<27} {'successor':<16} {'median':>8} {'n':>5} {'exact@4.0':>10} {'staff5Lines':>12}")
    print("-" * 84)

    results = []
    for font_name in font_names:
        result = analyze(font_name, references, args.verbose, finale_names)
        results.append(result)
        if result["status"] != "ok":
            print(f"{font_name:<27} {result['status']}")
            continue
        median = f"{result['median']:.4f}" if "median" in result else "-"
        if not result.get("successor_available", True):
            exact = "(not installed)"
        elif "exact" in result:
            exact = f"{result['exact']}/{result['samples']} ({result['exact_fraction'] * 100:.0f}%)"
        else:
            exact = "-"
        anchor = f"{result['staff5Lines']:.4f}" if result["staff5Lines"] else "-"
        print(
            f"{font_name:<27} {result['successor'] or '-':<16} {median:>8} "
            f"{result.get('samples', 0):>5} {exact:>10} {anchor:>12}"
        )

    if args.json:
        args.json.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    if args.check:
        return check_against_committed(results)

    return 0


def check_against_committed(results: List[dict]) -> int:
    """Flag any committed value the measurements no longer support.

    A committed 4.0 is corroborated by either an exact-match cluster against the
    successor font or the independent staff5Lines anchor. A committed null just
    has to stay unsupported. A value that measurement cannot corroborate is
    allowed only when sizeNotes explains the inference, so an undocumented guess
    still fails. Fonts that are not installed cannot be checked.
    """
    problems = []
    inferred = []
    skipped = 0
    for result in results:
        metadata = committed_metadata(SOURCE_DIR / f"{result['font']}.json")
        expected = metadata.get("staffSpacesPerEm")
        notes = metadata.get("sizeNotes", "")
        if result["status"] != "ok":
            skipped += 1
            continue
        supported = (
            result.get("exact_fraction", 0) >= 0.10
            or (result["staff5Lines"] is not None and abs(result["staff5Lines"] - 4.0) < 0.15)
        )
        evidence = (
            f"exact {result.get('exact', 0)}/{result.get('samples', 0)}, "
            f"median {result.get('median')}, anchor {result['staff5Lines']}"
        )
        if expected is None and supported:
            problems.append(
                f"{result['font']}: committed null, but measurements support 4.0 ({evidence})"
            )
        elif expected is not None and not supported:
            if notes:
                inferred.append(f"{result['font']}: committed {expected} ({evidence})")
            else:
                problems.append(
                    f"{result['font']}: committed {expected}, but measurements do not "
                    f"corroborate it ({evidence}) and sizeNotes is empty. Either "
                    f"measure the value or record in sizeNotes why it was inferred."
                )

    print()
    if skipped:
        print(f"Skipped {skipped} font(s) that are not installed.")
    if inferred:
        print(f"Inferred rather than measured, documented in sizeNotes ({len(inferred)}):")
        for message in inferred:
            print(f"  - {message}")
    if problems:
        print("Committed values not corroborated by measurement:", file=sys.stderr)
        for message in problems:
            print(f"  - {message}", file=sys.stderr)
        return 1
    print("All committed values are corroborated by measurement or documented as inferred.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
