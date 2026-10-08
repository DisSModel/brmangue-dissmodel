# Changelog

## [0.5.0] — 2026-10-08

### Changed (breaking)
- English names shared with `brmangue-terrame`, so the Python and Lua codes can be
  compared line by line (see "Naming" in the README). Results are unchanged.
  - Parameters: `taxa_elevacao` → `sea_level_rise_rate`, `altura_mare` →
    `tide_height`, `acrecao_ativa` → `accretion_enabled`; vector models:
    `attr_uso`/`attr_solo`/`attr_alt` → `land_use_attr`/`soil_attr`/`altitude_attr`.
    Executors reject the old names with a message giving the new one, instead of
    silently falling back to the defaults.
  - Constants in `brmangue.common.constants`: `MANGUE` → `MANGROVE`, `MAR` → `SEA`,
    `VEGETACAO_TERRESTRE` → `TERRESTRIAL_VEGETATION`, `SOLO_DESCOBERTO` →
    `BARE_SOIL`, `MANGUE_MIGRADO` → `MIGRATED_MANGROVE`, `USOS_INUNDADOS` →
    `FLOODED_USES`, `REGRAS_INUNDACAO` → `FLOODING_RULES`, `SOLO_*` → `SOIL_*`
    (`SOLO_MANGUE_MIGRADO` → `SOIL_MIGRATED_MANGROVE`, `SOLO_CANAL_FLUVIAL` →
    `SOIL_RIVER_CHANNEL`…), `USO_LABELS`/`USO_COLORS` → `USE_LABELS`/`USE_COLORS`.
  - Map labels in English.
  - The data attribute names (`uso`, `solo`, `alt`) are written only in
    `brmangue.common.constants` (`LAND_USE`, `SOIL`, `ALTITUDE`, and `past()` for
    the `<name>_past` snapshot); models, executors and tests use the constants,
    and local names are in English (`land_use_past`, `soil_new`…). Renaming the
    data now means changing those three lines (checked by renaming every data
    file to English in a copy: the tests and outputs are unchanged).
  - Unchanged: band/column names (`uso`, `solo`, `alt`), class codes, golden files.

### Fixed
- `pyproject.toml` required `dissmodel>=0.4.0`, but the models need the
  `SyncRasterModel`/`SyncSpatialModel` API of dissmodel 0.6 (12 of the 32 tests
  fail on 0.5.x); the requirement is now `dissmodel>=0.6.0`.

### Added
- Flooding scenario validated against TerraME: golden files in
  `tests/fixtures/golden_flood/` and `tests/test_flood_validation.py`.

## [0.4.0] and earlier
See the GitHub releases.
