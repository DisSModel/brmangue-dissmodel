"""
tests/test_level1.py — Level 1: Analytical tests on minimal grids
==================================================================

Each test builds a 3×3 grid with fully controlled initial state,
computes the expected result by hand, and asserts that the
Raster implementation produces the expected output.

Grid layout (row, col):
    (0,0) (0,1) (0,2)
    (1,0) (1,1) (1,2)
    (2,0) (2,1) (2,2)

Center cell = index (1,1) = GDF row 4 (row-major order).

Run with:
    pytest tests/test_level1.py -v
"""
from __future__ import annotations

import numpy as np
import pytest

from dissmodel.core import Environment
from dissmodel.geo.raster.backend import RasterBackend

from brmangue.models.raster.flood_model    import FloodModel    as RasterFlood
from brmangue.models.raster.mangrove_model import MangroveModel as RasterMangrove

from brmangue.common.constants import (
    SEA, MANGROVE, MIGRATED_MANGROVE, FLOODED_MANGROVE,
    TERRESTRIAL_VEGETATION, FLOODED_TERRESTRIAL_VEGETATION,
    BARE_SOIL, FLOODED_SOIL,
    ANTHROPIZED_AREA, FLOODED_ANTHROPIZED_AREA,
    SOIL_MANGROVE, SOIL_MIGRATED_MANGROVE, SOIL_RIVER_CHANNEL, SOIL_OTHER,
)
from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL

# ── helpers ───────────────────────────────────────────────────────────────────

CELL_SIZE = 1.0   # 1 m cells — keeps coordinates simple


def make_backend(land_use: list[int], alt: list[float], soil: list[int]) -> RasterBackend:
    """Build a 3×3 RasterBackend from flat lists (row-major order)."""
    assert len(land_use) == len(alt) == len(soil) == 9
    shape = (3, 3)
    backend = RasterBackend(shape=shape)
    backend.set(LAND_USE,  np.array(land_use,  dtype=np.int16).reshape(shape))
    backend.set(ALTITUDE,  np.array(alt,  dtype=np.float32).reshape(shape))
    backend.set(SOIL, np.array(soil, dtype=np.int16).reshape(shape))
    mask = np.ones(shape, dtype=bool)
    backend.set("mask", mask)
    return backend


def run_raster(backend: RasterBackend, model_cls, n_steps: int = 1, **kwargs):
    """Run a single raster model for n_steps and return the backend."""
    env = Environment(start_time=1, end_time=n_steps)
    model_cls(backend=backend, **kwargs)
    env.run()
    return backend


# ── FloodModel tests ──────────────────────────────────────────────────────────

class TestFloodModel:
    """
    Analytical tests for FloodModel (raster).

    All expected values are derived from the flood.lua rules (brmangue-terrame):
      1. Elevation diffusion (relative condition — flow shared between
         source and low neighbors)
      2. Flooding (absolute condition — alt <= sea_level)
    """

    def test_no_sea_cell_no_change(self):
        """
        If no cell is SEA or flooded, nothing should change.

        Expected: all uso and alt values remain identical after 1 step.
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [5.0] * 9
        soil = [SOIL_OTHER] * 9

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterFlood, sea_level_rise_rate=0.011)

        assert (backend.get(LAND_USE) == TERRESTRIAL_VEGETATION).all(), \
            "Raster: uso should not change without a sea source"
        assert (backend.get(ALTITUDE) == 5.0).all(), \
            "Raster: alt should not change without a sea source"

    def test_sea_cell_floods_low_neighbor(self):
        """
        Center (1,1): SEA, alt=0.
        All 8 neighbors: TERRESTRIAL_VEGETATION, alt=0.005.

        sea_level = 1 * 0.011 = 0.011
        Neighbors (0.005) <= sea_level → all 8 flood: FLOODED_TERRESTRIAL_VEGETATION

        Elevation diffusion:
        neighbors alt (0.005) > center alt (0.0) → NOT lower than source
        lower_neighbors = 1 (only center itself)
        flux = 0.011 / 1 = 0.011 → goes entirely to center
        neighbor alt: unchanged (0.005)
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [0.005] * 9
        soil = [SOIL_OTHER] * 9
        land_use[4] = SEA
        alt[4] = 0.0

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterFlood, sea_level_rise_rate=0.011)

        expected_land_use = [FLOODED_TERRESTRIAL_VEGETATION] * 9
        expected_land_use[4] = SEA

        assert list(backend.get(LAND_USE).flatten()) == expected_land_use, \
            f"Raster uso mismatch: {list(backend.get(LAND_USE).flatten())} != {expected_land_use}"

        # center absorbs full flux; neighbors are higher so receive nothing
        assert backend.get(ALTITUDE)[1, 1] == pytest.approx(0.011, abs=1e-5), \
            "Raster: center alt wrong"

        assert np.allclose(
            backend.get(ALTITUDE).flatten()[[0,1,2,3,5,6,7,8]],
            0.005, atol=1e-5
        ), "Raster: neighbor alt should be unchanged"


    def test_flux_spreads_to_lower_neighbors(self):
        """
        Tests elevation diffusion when neighbors ARE lower than the source.

        Center (1,1): SEA, alt=0.1.
        All 8 neighbors: TERRESTRIAL_VEGETATION, alt=0.0.

        sea_level = 0.011 — neighbors (0.0) <= sea_level → flood
        Diffusion: neighbors (0.0) <= center (0.1) → lower_neighbors = 9
        flux = 0.011 / 9 ≈ 0.001222
        center alt:   0.1   + 0.001222 = 0.101222
        neighbor alt: 0.0   + 0.001222 = 0.001222
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [0.0] * 9
        soil = [SOIL_OTHER] * 9
        land_use[4] = SEA
        alt[4] = 0.1

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterFlood, sea_level_rise_rate=0.011)

        flux = 0.011 / 9

        assert backend.get(ALTITUDE)[1, 1] == pytest.approx(0.1 + flux, abs=1e-5), \
            "Raster: center alt wrong"

        assert np.allclose(
            backend.get(ALTITUDE).flatten()[[0,1,2,3,5,6,7,8]],
            flux, atol=1e-5
        ), "Raster: neighbor alt wrong"

    def test_high_neighbor_not_flooded(self):
        """
        Center (1,1): SEA, alt=0.
        All neighbors: TERRESTRIAL_VEGETATION, alt=10.0.

        sea_level = 0.011 — neighbors (10.0) >> sea_level → no flooding.
        Elevation: neighbors are NOT lower than center (10 > 0),
        so lower_neighbors = 1 (only center itself).
        flux = 0.011 / 1 = 0.011 → goes entirely to center.
        No neighbor gets extra altitude.
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [10.0] * 9
        soil = [SOIL_OTHER] * 9
        land_use[4] = SEA
        alt[4] = 0.0

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterFlood, sea_level_rise_rate=0.011)

        # uso: no neighbor should be flooded
        assert (backend.get(LAND_USE).flatten()[[0,1,2,3,5,6,7,8]] == TERRESTRIAL_VEGETATION).all(), \
               "Raster: no neighbor should be flooded"

        # elevation: center absorbs all flow, neighbors unchanged
        assert backend.get(ALTITUDE)[1, 1] == pytest.approx(0.011, abs=1e-5), \
            "Raster: center alt should be 0.011"

    def test_raster_smoke_random(self):
        """
        Smoke test: run raster on a random but deterministic 3×3 grid.
        """
        rng  = np.random.default_rng(42)
        land_use  = rng.choice([SEA, TERRESTRIAL_VEGETATION, ANTHROPIZED_AREA], size=9).tolist()
        alt  = rng.uniform(0.0, 0.02, size=9).tolist()
        soil = [SOIL_OTHER] * 9

        backend = make_backend(list(land_use), list(alt), list(soil))
        run_raster(backend, RasterFlood, sea_level_rise_rate=0.011)

        ras_land_use = list(backend.get(LAND_USE).flatten())
        assert len(ras_land_use) == 9


# ── MangroveModel tests ───────────────────────────────────────────────────────

class TestMangroveModel:
    """
    Analytical tests for MangroveModel (raster).

    Rules from mangrove.lua (brmangue-terrame):
      migrateSoils: source soil (MANGROVE/MIGRADO/CANAL) → neighbor with
                    TARGET_USE and alt <= influence_zone becomes SOIL_MIGRATED_MANGROVE
      migrateUses:  source use (MANGROVE/MIGRADO) → neighbor with
                    TARGET_USE + MANGROVE_SOIL + alt <= influence_zone becomes MIGRATED_MANGROVE
    """

    def test_no_source_no_migration(self):
        """
        If no cell has a source soil or source use, nothing migrates.
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [1.0] * 9
        soil = [SOIL_OTHER] * 9

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterMangrove, sea_level_rise_rate=0.011, tide_height=6.0)

        assert (backend.get(LAND_USE)  == TERRESTRIAL_VEGETATION).all(), "Raster: uso unchanged"
        assert (backend.get(SOIL) == SOIL_OTHER).all(),         "Raster: solo unchanged"

    def test_soil_migration_triggered(self):
        """
        Center (1,1): MANGROVE, SOIL_MANGROVE, alt=1.0 (source cell).
        All neighbors: TERRESTRIAL_VEGETATION, SOIL_OTHER, alt=1.0.

        influence_zone = 6.0 + 1*0.011 = 6.011
        alt (1.0) <= influence_zone (6.011) → condition met
        neighbor solo != SOIL_MIGRATED_MANGROVE → condition met
        neighbor uso in TARGET_USES → condition met

        Expected: all 8 neighbors → solo = SOIL_MIGRATED_MANGROVE
        uso of neighbors stays TERRESTRIAL_VEGETATION (migrateUses requires
        neighbor solo in MANGROVE_SOILS — which was SOIL_OTHER in solo_past)
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [1.0] * 9
        soil = [SOIL_OTHER] * 9
        land_use[4]  = MANGROVE
        soil[4] = SOIL_MANGROVE

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterMangrove, sea_level_rise_rate=0.011, tide_height=6.0)

        # solo: all neighbors become SOIL_MIGRATED_MANGROVE; center unchanged
        expected_soil = [SOIL_MIGRATED_MANGROVE] * 9
        expected_soil[4] = SOIL_MANGROVE

        assert list(backend.get(SOIL).flatten()) == expected_soil, \
            f"Raster solo: {list(backend.get(SOIL).flatten())} != {expected_soil}"

        # uso: neighbors stay TERRESTRIAL_VEGETATION (solo_past was SOIL_OTHER)
        assert (backend.get(LAND_USE).flatten()[[0,1,2,3,5,6,7,8]] == TERRESTRIAL_VEGETATION).all(), \
            "Raster: neighbor uso should not migrate yet (solo_past=OUTROS)"

    def test_use_migration_requires_mangrove_soil(self):
        """
        Center: MANGROVE, SOIL_MANGROVE, alt=1.0.
        Neighbors: TERRESTRIAL_VEGETATION, SOIL_MANGROVE (already mangrove soil), alt=1.0.

        In this case solo_past IS in MANGROVE_SOILS → migrateUses triggers.
        Expected: all 8 neighbors → uso = MIGRATED_MANGROVE
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [1.0] * 9
        soil = [SOIL_MANGROVE] * 9    # all cells already have mangrove soil
        land_use[4] = MANGROVE

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterMangrove, sea_level_rise_rate=0.011, tide_height=6.0)

        expected_land_use = [MIGRATED_MANGROVE] * 9
        expected_land_use[4] = MANGROVE

        assert list(backend.get(LAND_USE).flatten()) == expected_land_use, \
            f"Raster uso: {list(backend.get(LAND_USE).flatten())} != {expected_land_use}"

    def test_high_altitude_blocks_migration(self):
        """
        Center: MANGROVE, SOIL_MANGROVE, alt=1.0.
        Neighbors: TERRESTRIAL_VEGETATION, SOIL_MANGROVE, alt=100.0.

        influence_zone = 6.011. Neighbor alt (100.0) > influence_zone → migration blocked.
        Expected: nothing changes.
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [100.0] * 9
        soil = [SOIL_MANGROVE] * 9
        land_use[4]  = MANGROVE
        alt[4]  = 1.0

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterMangrove, sea_level_rise_rate=0.011, tide_height=6.0)

        assert (backend.get(LAND_USE).flatten()[[0,1,2,3,5,6,7,8]] == TERRESTRIAL_VEGETATION).all(), \
            "Raster: neighbor uso should not migrate (alt too high)"

    def test_raster_smoke_mixed_grid(self):
        """
        Smoke test: run raster on a deterministic mixed grid.
        """
        land_use  = [TERRESTRIAL_VEGETATION, MANGROVE,             TERRESTRIAL_VEGETATION,
                BARE_SOIL,     MIGRATED_MANGROVE,     TERRESTRIAL_VEGETATION,
                TERRESTRIAL_VEGETATION, TERRESTRIAL_VEGETATION, BARE_SOIL]
        alt  = [1.0] * 9
        soil = [SOIL_MANGROVE,    SOIL_MANGROVE,         SOIL_MANGROVE,
                SOIL_MANGROVE,    SOIL_MANGROVE,         SOIL_MIGRATED_MANGROVE,
                SOIL_RIVER_CHANNEL, SOIL_OTHER,     SOIL_OTHER]

        backend = make_backend(list(land_use), list(alt), list(soil))
        run_raster(backend, RasterMangrove, n_steps=3, sea_level_rise_rate=0.011, tide_height=6.0)

        ras_land_use  = list(backend.get(LAND_USE).flatten())
        ras_soil = list(backend.get(SOIL).flatten())
        assert len(ras_land_use) == 9
        assert len(ras_soil) == 9


# ── cross-model invariants ────────────────────────────────────────────────────

class TestInvariants:
    """
    Properties that must hold by construction regardless of input.
    """

    def test_flooded_cells_monotonically_nondecreasing(self):
        """
        Once a cell is flooded, it should not revert to a dry state
        (no accretion active, no drainage rule).
        """
        land_use  = [TERRESTRIAL_VEGETATION] * 9
        alt  = [0.005] * 9
        soil = [SOIL_OTHER] * 9
        land_use[4] = SEA
        alt[4] = 0.0

        from brmangue.common.constants import FLOODED_USES

        backend = make_backend(land_use, alt, soil)

        n_steps = 5
        env_ras = Environment(start_time=1, end_time=n_steps)

        flood_ras = RasterFlood(backend=backend, sea_level_rise_rate=0.011)

        # track flooded count each step
        flooded_ras_counts = []

        original_ras_execute = flood_ras.execute

        def patched_ras():
            original_ras_execute()
            flooded_ras_counts.append(int(np.isin(backend.get(LAND_USE), FLOODED_USES).sum()))

        flood_ras.execute = patched_ras

        env_ras.run()

        for i in range(1, len(flooded_ras_counts)):
            assert flooded_ras_counts[i] >= flooded_ras_counts[i - 1], \
                f"Raster: flooded count decreased at step {i+1}"

    def test_land_use_values_always_valid(self):
        """
        After any number of steps, uso values must remain within the
        set of valid land-use codes {1..10}.
        """
        valid_land_use_values = set(range(1, 11))

        land_use  = [TERRESTRIAL_VEGETATION, SEA, MANGROVE,
                ANTHROPIZED_AREA,   SEA,  BARE_SOIL,
                MANGROVE,             SEA,  TERRESTRIAL_VEGETATION]
        alt  = [0.01] * 9
        soil = [SOIL_MANGROVE] * 9

        backend = make_backend(land_use, alt, soil)
        run_raster(backend, RasterFlood, n_steps=5, sea_level_rise_rate=0.011)

        ras_invalid = set(backend.get(LAND_USE).flatten().tolist()) - valid_land_use_values

        assert not ras_invalid, f"Raster: invalid uso values found: {ras_invalid}"
