"""
brmangue/constants.py — BR-MANGUE Domain Constants
=========================================================
Land-use and soil classes of the original Lua model (Bezerra, 2014). Names follow
the glossary shared with brmangue-terrame (LambdaGeo/brmangue-terrame): the same
class names as its `land_use_classes` / `soil_classes` tables, with a SOIL_
prefix for soils. The codes are those of the data and never change.
CRS and geographic parameters for Maranhão Island.
"""
from __future__ import annotations

# ── data attribute / band names ───────────────────────────────────────────────
# The only place where the names of the data attributes are written. The code
# refers to them through these constants, so if the data are renamed (e.g. to
# English) only these three lines change. Input files with other names can
# also be mapped at run time with `column_map` (vector) or `band_map` (GeoTIFF).
LAND_USE = "uso"
SOIL     = "solo"
ALTITUDE = "alt"

STATE_ATTRIBUTES: tuple[str, ...] = (LAND_USE, ALTITUDE, SOIL)

# dissmodel's SyncRasterModel / SyncSpatialModel keep the start-of-step state
# of each attribute in "<name>_past" (TerraME: cell.past[name]).
PAST_SUFFIX = "_past"


def past(name: str) -> str:
    """Name of the start-of-step snapshot of an attribute, e.g. ``"uso_past"``."""
    return name + PAST_SUFFIX


# ── land-use classes (land_use_classes in brmangue-terrame) ───────────────────────────────────────────────────────────────
MANGROVE                    = 1
TERRESTRIAL_VEGETATION       = 2
SEA                       = 3
ANTHROPIZED_AREA          = 4
BARE_SOIL           = 5
FLOODED_SOIL             = 6
FLOODED_ANTHROPIZED_AREA = 7
MIGRATED_MANGROVE            = 8
FLOODED_MANGROVE           = 9
FLOODED_TERRESTRIAL_VEGETATION    = 10

FLOODED_USES: list[int] = [
    SEA, FLOODED_SOIL, FLOODED_ANTHROPIZED_AREA,
    FLOODED_MANGROVE, FLOODED_TERRESTRIAL_VEGETATION,
]

# dry → flooded (Bezerra 2014)
FLOODING_RULES: dict[int, int] = {
    MANGROVE:              FLOODED_MANGROVE,
    MIGRATED_MANGROVE:      FLOODED_MANGROVE,
    TERRESTRIAL_VEGETATION: FLOODED_TERRESTRIAL_VEGETATION,
    ANTHROPIZED_AREA:    FLOODED_ANTHROPIZED_AREA,
    BARE_SOIL:     FLOODED_SOIL,
}

USE_LABELS: dict[int, str] = {
    MANGROVE:                    "Mangrove",
    TERRESTRIAL_VEGETATION:       "Terrestrial vegetation",
    SEA:                       "Sea",
    ANTHROPIZED_AREA:          "Anthropized area",
    BARE_SOIL:           "Bare soil",
    FLOODED_SOIL:             "Flooded soil",
    FLOODED_ANTHROPIZED_AREA: "Flooded anthropized area",
    MIGRATED_MANGROVE:            "Migrated mangrove",
    FLOODED_MANGROVE:           "Flooded mangrove",
    FLOODED_TERRESTRIAL_VEGETATION:    "Flooded terrestrial vegetation",
}

# exact colours of the Lua model (land_use_classes RGB → hex)
USE_COLORS: dict[int, str] = {
    MANGROVE:                    "#006400",
    TERRESTRIAL_VEGETATION:       "#808000",
    SEA:                       "#00008b",
    ANTHROPIZED_AREA:          "#ffd700",
    BARE_SOIL:           "#ffdead",
    FLOODED_SOIL:             "#000000",
    FLOODED_ANTHROPIZED_AREA: "#323232",
    MIGRATED_MANGROVE:            "#00ff00",
    FLOODED_MANGROVE:           "#ff0000",
    FLOODED_TERRESTRIAL_VEGETATION:    "#000000",
}

# ── soil classes (soil_classes in brmangue-terrame) ──────────────────────────────────────────────────────────────
SOIL_RIVER_CHANNEL  = 0
SOIL_RIVERBED      = 1   # present in input data — no active rule (legacy class)
SOIL_PODZOLIC      = 2   # present in input data — no active rule (legacy class)
SOIL_MANGROVE         = 3
SOIL_OTHER         = 4
SOIL_MIGRATED_MANGROVE = 9

# All soil codes present in the input data. Values 1 and 2 are legacy classes
# from the original Bezerra (2014) database that carry no transition rule in
# the current model — they are treated as passive substrate (like SOIL_OTHER).
VALID_SOILS: set[int] = {
    SOIL_RIVER_CHANNEL,
    SOIL_RIVERBED,
    SOIL_PODZOLIC,
    SOIL_MANGROVE,
    SOIL_OTHER,
    SOIL_MIGRATED_MANGROVE,
}

SOIL_LABELS: dict[int, str] = {
    SOIL_RIVER_CHANNEL:  "River channel",
    SOIL_RIVERBED:      "Riverbed",
    SOIL_PODZOLIC:      "Podzolic",
    SOIL_MANGROVE:         "Mangrove mud",
    SOIL_MIGRATED_MANGROVE: "Migrated mangrove mud",
    SOIL_OTHER:         "Other",
}

# ── geography — Maranhão Island ──────────────────────────────────────────────
ORIGIN_X  = 500_000.0    # UTM Easting  (SIRGAS 2000 / UTM 24S)
ORIGIN_Y  = 9_700_000.0  # UTM Northing
CRS       = "EPSG:31984"
CELL_SIZE = 100.0         # metres

# ── GeoTIFF: band specification (name, numpy dtype, nodata) ───────────────────
TIFF_BANDS: list[tuple[str, str, float]] = [
    (LAND_USE, "int16",   0),
    (ALTITUDE, "float32", -9999.0),
    (SOIL,     "int16",   -1),
]

# soil colours (for RasterMap)
SOIL_COLORS: dict[int, str] = {
    SOIL_RIVER_CHANNEL:  "#0000ff",   # blue — drainage channel
    SOIL_RIVERBED:      "#6699cc",   # light blue
    SOIL_PODZOLIC:      "#aaaaaa",   # light grey
    SOIL_MANGROVE:         "#006400",   # dark green
    SOIL_MIGRATED_MANGROVE: "#228b22",   # forest green
    SOIL_OTHER:         "#888888",   # grey
}