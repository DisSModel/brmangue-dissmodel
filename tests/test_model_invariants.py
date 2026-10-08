"""
tests/test_level3_invariants.py — Level 3: Structural invariants
=================================================================

Properties that must hold by construction across any input and any
number of steps. These tests do not compare against a reference —
they verify that the model never violates its own rules.

Invariants tested:
    1. uso and solo values always stay within their valid domains
    2. Flooded cells are monotonically non-decreasing
    3. Soil migration is irreversible (SOIL_MIGRATED_MANGROVE never reverts)
    4. Mangrove area (MANGROVE + MIGRATED_MANGROVE + FLOODED_MANGROVE) is non-decreasing
    5. zonaInfluencia is monotonically increasing (deterministic driver)
    6. Cells outside the mask never change state

All tests run on a realistic 5×5 grid loaded from the shapefile fixture,
so invariants are checked against real geographic data, not toy grids.

Run with:
    python -m pytest tests/test_level3_invariants.py -v
"""
from __future__ import annotations

import pathlib

import geopandas as gpd
import numpy as np
import pytest

from dissmodel.core               import Environment
from dissmodel.geo.raster.backend import RasterBackend

from brmangue.models.raster.flood_model    import FloodModel
from brmangue.models.raster.mangrove_model import MangroveModel

from brmangue.common.constants import (
    FLOODED_USES,
    MANGROVE, MIGRATED_MANGROVE, FLOODED_MANGROVE,
    SOIL_MANGROVE, SOIL_MIGRATED_MANGROVE, SOIL_RIVER_CHANNEL, SOIL_OTHER,
    VALID_SOILS,   # ← importar daqui
)
from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL

# ── paths ─────────────────────────────────────────────────────────────────────

# Input data lives in examples/data/input — no duplication in tests/fixtures
INPUT_ZIP = (
    pathlib.Path(__file__).parent.parent / "examples" / "data" / "input" / "elevacao_pol.zip"
)

# ── model parameters ──────────────────────────────────────────────────────────

SEA_LEVEL_RISE_RATE = 0.05
TIDE_HEIGHT   = 6.0
N_STEPS       = 30

# ── valid domains ─────────────────────────────────────────────────────────────

VALID_USES  = set(range(1, 11))           # {1 … 10}

MANGROVE_SET = {MANGROVE, MIGRATED_MANGROVE, FLOODED_MANGROVE}

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def backend_sequence():
    """
    Run the full simulation and return a list of (land use, soil, altitude) snapshots,
    one per step, plus the mask.

    scope=module: the simulation runs once and all tests share the results.
    """
    if not INPUT_ZIP.exists():
        pytest.skip(f"Input data not found: {INPUT_ZIP}")

    gdf = gpd.read_file(INPUT_ZIP)
    gdf.columns = [c.lower() for c in gdf.columns]
    gdf = gdf.sort_values(["row", "col"]).reset_index(drop=True)

    backend = _build_backend(gdf)

    snapshots: list[dict[str, np.ndarray]] = []

    # patch execute to capture state after each step
    env       = Environment(start_time=1, end_time=N_STEPS)
    flood     = FloodModel(backend=backend, sea_level_rise_rate=SEA_LEVEL_RISE_RATE)
    mangrove  = MangroveModel(
        backend       = backend,
        sea_level_rise_rate = SEA_LEVEL_RISE_RATE,
        tide_height   = TIDE_HEIGHT,
    )

    orig_mangrove_execute = mangrove.execute

    def patched_mangrove():
        orig_mangrove_execute()
        snapshots.append({
            LAND_USE:  backend.get(LAND_USE).copy(),
            SOIL: backend.get(SOIL).copy(),
            ALTITUDE:  backend.get(ALTITUDE).copy(),
        })

    mangrove.execute = patched_mangrove
    env.run()

    mask = backend.arrays.get("mask", np.ones(backend.shape, dtype=bool)).astype(bool)
    return snapshots, mask


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_backend(gdf: gpd.GeoDataFrame) -> RasterBackend:
    rows = gdf["row"].astype(int).values
    cols = gdf["col"].astype(int).values
    rows = rows - rows.min()
    cols = cols - cols.min()

    n_rows = int(rows.max()) + 1
    n_cols = int(cols.max()) + 1

    backend = RasterBackend(shape=(n_rows, n_cols))

    mask = np.zeros((n_rows, n_cols), dtype=bool)
    mask[rows, cols] = True
    backend.set("mask", mask)

    for band in (LAND_USE, ALTITUDE, SOIL):
        arr = np.zeros((n_rows, n_cols), dtype=np.float32)
        arr[rows, cols] = gdf[band].astype(float).values
        backend.set(band, arr)

    return backend


# ── invariant 1: valid domains ────────────────────────────────────────────────

def test_land_use_always_within_valid_domain(backend_sequence):
    """
    uso must always be in {1..10} for every valid cell at every step.
    """
    snapshots, mask = backend_sequence
    for step, snap in enumerate(snapshots, start=1):
        land_use_vals = set(snap[LAND_USE][mask].astype(int).tolist())
        invalid  = land_use_vals - VALID_USES
        assert not invalid, (
            f"Step {step:02d}: uso has invalid values {invalid}. "
            f"Valid domain is {VALID_USES}."
        )


def test_soil_always_within_valid_domain(backend_sequence):
    """
    solo must always be in {0, 3, 4, 9} for every valid cell at every step.
    """
    snapshots, mask = backend_sequence
    for step, snap in enumerate(snapshots, start=1):
        soil_vals = set(snap[SOIL][mask].astype(int).tolist())
        invalid   = soil_vals - VALID_SOILS
        assert not invalid, (
            f"Step {step:02d}: solo has invalid values {invalid}. "
            f"Valid domain is {VALID_SOILS}."
        )


# ── invariant 2: flooded cells are non-decreasing ────────────────────────────

def test_flooded_cells_monotonically_nondecreasing(backend_sequence):
    """
    The count of flooded cells (all FLOODED_USES) must never decrease.
    Once a cell is flooded, it cannot revert (no accretion, no drainage).
    """
    snapshots, mask = backend_sequence
    counts = [
        int(np.isin(snap[LAND_USE][mask], FLOODED_USES).sum())
        for snap in snapshots
    ]
    for i in range(1, len(counts)):
        assert counts[i] >= counts[i - 1], (
            f"Flooded cell count decreased at step {i+1}: "
            f"{counts[i-1]} → {counts[i]}"
        )


# ── invariant 3: soil migration is irreversible ───────────────────────────────

def test_soil_migrated_mangrove_never_reverts(backend_sequence):
    """
    Once a cell reaches SOIL_MIGRATED_MANGROVE, its soil type must not
    change to any other value in subsequent steps.
    """
    snapshots, mask = backend_sequence
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1][SOIL]
        curr = snapshots[i][SOIL]

        was_migrated = (prev == SOIL_MIGRATED_MANGROVE) & mask
        reverted    = was_migrated & (curr != SOIL_MIGRATED_MANGROVE)

        n_reverted = int(reverted.sum())
        assert n_reverted == 0, (
            f"Step {i+1:02d}: {n_reverted} cells reverted from "
            f"SOIL_MIGRATED_MANGROVE to another soil type."
        )


# ── invariant 4: mangrove area is non-decreasing ─────────────────────────────

def test_mangrove_area_nondecreasing(backend_sequence):
    """
    The total mangrove footprint (MANGROVE + MIGRATED_MANGROVE + FLOODED_MANGROVE)
    must be monotonically non-decreasing.

    Rationale: mangrove cells can migrate or flood, but the model has
    no mechanism to eliminate mangrove cover entirely — only to transform
    it into another mangrove state.
    """
    snapshots, mask = backend_sequence
    counts = [
        int(np.isin(snap[LAND_USE][mask], list(MANGROVE_SET)).sum())
        for snap in snapshots
    ]
    for i in range(1, len(counts)):
        assert counts[i] >= counts[i - 1], (
            f"Mangrove area decreased at step {i+1}: "
            f"{counts[i-1]} → {counts[i]} cells"
        )


# ── invariant 5: the tidal influence zone is strictly increasing ───────────────────

def test_zona_influencia_strictly_increasing():
    """
    zonaInfluencia = tide_height + t * sea_level_rise_rate is a strictly
    increasing function of time — a deterministic property of the driver.

    This test does not run the model; it verifies the formula directly.
    """
    influence_zone_prev = TIDE_HEIGHT
    for t in range(1, N_STEPS + 1):
        influence_zone = TIDE_HEIGHT + t * SEA_LEVEL_RISE_RATE
        assert influence_zone > influence_zone_prev, (
            f"zonaInfluencia not strictly increasing at t={t}: "
            f"{influence_zone_prev} → {influence_zone}"
        )
        influence_zone_prev = influence_zone


# ── invariant 6: cells outside mask never change ─────────────────────────────

def test_masked_cells_never_change(backend_sequence):
    """
    Cells outside the valid mask must retain their initial values
    (zero by construction) across all steps.
    """
    snapshots, mask = backend_sequence
    outside = ~mask

    # initial state for outside cells is zero (set in _build_backend)
    for step, snap in enumerate(snapshots, start=1):
        for band in (LAND_USE, SOIL):
            vals = snap[band][outside]
            assert (vals == 0).all(), (
                f"Step {step:02d}: band '{band}' has non-zero values "
                f"outside the mask — {int((vals != 0).sum())} cells affected."
            )

# ══════════════════════════════════════════════════════════════════════════════
# Regression: checkpoint metrics must be independent of end_time
# ══════════════════════════════════════════════════════════════════════════════
#
# Before the fix, the metrics loop read ``backend.get(band)`` AFTER ``env.run()``
# had finished, comparing the SAME final state against every golden CSV. The
# observable symptom was that the step=01 metric changed with end_time:
#
#     end_time=3   -> step=01  uso: match=99.4%
#     end_time=20  -> step=01  uso: match=98.9%
#
# ...which is impossible if it were really step 1. This test is the detector.

GOLDEN_DIR = pathlib.Path(__file__).parent / "fixtures" / "golden"


def _validation_metrics(end_time: int, checkpoints: list[int]) -> dict:
    from brmangue.executors.validation_executor import ValidationExecutor
    from dissmodel.executor import ExperimentRecord

    executor = ValidationExecutor()
    record = ExperimentRecord(
        model_name="validation",
        source={"uri": str(INPUT_ZIP)},
        parameters={
            "golden_dir":    str(GOLDEN_DIR),
            "end_time":      end_time,
            "sea_level_rise_rate": 0.05,
            "tide_height":   6.0,
            "checkpoints":   checkpoints,
        },
    )
    return executor.run(executor.load(record), record)["metrics"]


@pytest.mark.skipif(not INPUT_ZIP.exists(), reason=f"Input data not found: {INPUT_ZIP}")
@pytest.mark.skipif(not GOLDEN_DIR.exists(), reason=f"Golden dir not found: {GOLDEN_DIR}")
def test_checkpoint_metrics_independent_of_end_time():
    """step=01 must be identical whether running 3 steps or 19."""
    short = _validation_metrics(end_time=3,  checkpoints=[1])
    long_ = _validation_metrics(end_time=19, checkpoints=[1, 5, 10, 19])

    for band in (LAND_USE, SOIL, ALTITUDE):
        a = short["1"][band]
        b = long_["1"][band]
        assert a["match_pct"] == pytest.approx(b["match_pct"], abs=1e-9), (
            f"band {band}: step=01 match depends on end_time "
            f"({a['match_pct']:.4f}% with 3 steps vs {b['match_pct']:.4f}% with 19) "
            f"— the per-checkpoint snapshot is not being used"
        )
        assert a["mae"] == pytest.approx(b["mae"], abs=1e-12), (
            f"band {band}: step=01 MAE depends on end_time"
        )


# ══════════════════════════════════════════════════════════════════════════════
# Regression: categorical bands must match TerraME exactly
# ══════════════════════════════════════════════════════════════════════════════
#
# With the golden step offset applied (step_01.csv is the initial state, so
# simulation step N maps to step_{N+1}.csv), the categorical outputs agree with
# TerraME cell for cell. Any drift here is a real behavioural divergence, not
# rounding — these bands are integers.

@pytest.mark.skipif(not INPUT_ZIP.exists(), reason=f"Input data not found: {INPUT_ZIP}")
@pytest.mark.skipif(not GOLDEN_DIR.exists(), reason=f"Golden dir not found: {GOLDEN_DIR}")
@pytest.mark.parametrize("step", [1, 5, 10, 19])
def test_categorical_bands_match_terrame_exactly(step):
    """`uso` and `solo` must agree with TerraME on every cell."""
    metrics = _validation_metrics(end_time=19, checkpoints=[1, 5, 10, 19])

    for band in (LAND_USE, SOIL):
        m = metrics[str(step)][band]
        assert m["match_pct"] == pytest.approx(100.0, abs=1e-9), (
            f"step {step}, band {band}: match={m['match_pct']:.4f}% "
            f"(max_err={m['max_err']}). Categorical parity lost."
        )
        assert m["mae"] == pytest.approx(0.0, abs=1e-12), (
            f"step {step}, band {band}: MAE={m['mae']} — expected exact match"
        )


@pytest.mark.skipif(not INPUT_ZIP.exists(), reason=f"Input data not found: {INPUT_ZIP}")
@pytest.mark.skipif(not GOLDEN_DIR.exists(), reason=f"Golden dir not found: {GOLDEN_DIR}")
def test_flood_model_floods_with_laboratory_parameters():
    """FloodModel must trigger land-use transitions at the lab's sea-level rate.

    The reference scenario (`sea_level_rise_rate=0.05`) never floods a single cell:
    the lowest cell adjacent to a source sits at 1.0 m and the sea only reaches
    1.0 m at step 20, by which point flux diffusion has raised it further. The
    golden CSVs confirm TerraME behaves identically (0 newly flooded cells in
    all 20 steps), so the Python model is faithful — but that scenario leaves
    the flood component unexercised.

    The original laboratory script (`lab1.lua`) uses `TAXA_ELEVACAO_MAR = 0.5`
    with `FINAL_TIME = 11`. This test pins that the component does fire under
    those parameters, so the coverage gap cannot reappear silently.
    """
    import numpy as np
    from dissmodel.core import Environment
    from brmangue.executors.validation_executor import _build_raster
    from brmangue.models.raster.flood_model import FloodModel
    from brmangue.models.raster.mangrove_model import MangroveModel
    from dissmodel.io import load_dataset

    gdf, _ = load_dataset(str(INPUT_ZIP), fmt="vector")
    gdf.columns = [c.lower() for c in gdf.columns]
    gdf = gdf.sort_values(["row", "col"]).reset_index(drop=True)
    backend, _, _ = _build_raster(gdf)

    env = Environment(start_time=1, end_time=11)
    flood = FloodModel(backend=backend, sea_level_rise_rate=0.5)
    MangroveModel(backend=backend, sea_level_rise_rate=0.5, tide_height=6.0)
    env.run()

    assert flood.flooded_cells > 0, (
        "FloodModel flooded no cells even at the laboratory sea-level rate "
        "(sea_level_rise_rate=0.5, 11 steps). The flood component is not firing."
    )


def test_flood_flux_counts_only_real_neighbours():
    """A corner sea cell has 3 real neighbours, so flux = taxa / (1 + 3).

    Regression: padding cells (alt=0) used to count as "lower neighbours",
    diluting the flux along grid/polygon borders (TerraME only has real ones).
    """
    import numpy as np
    from dissmodel.core import Environment
    from dissmodel.geo.raster.backend import RasterBackend
    from brmangue.models.raster.flood_model import FloodModel

    b = RasterBackend(shape=(3, 3))
    land_use = np.full((3, 3), 2, dtype=np.int16)
    land_use[0, 0] = 3                                  # sea in the corner
    b.set(LAND_USE, land_use)
    b.set(ALTITUDE, np.full((3, 3), 5.0))
    b.set("mask", np.ones((3, 3), dtype=bool))
    env = Environment(start_time=1, end_time=1)
    FloodModel(backend=b, sea_level_rise_rate=0.4)
    env.run()
    alt = b.get(ALTITUDE)
    assert abs(alt[0, 0] - (5.0 + 0.4 / 4)) < 1e-9
    assert abs(alt[0, 1] - (5.0 + 0.4 / 4)) < 1e-9
