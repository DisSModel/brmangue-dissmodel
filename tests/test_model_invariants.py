"""
tests/test_level3_invariants.py — Level 3: Structural invariants
=================================================================

Properties that must hold by construction across any input and any
number of steps. These tests do not compare against a reference —
they verify that the model never violates its own rules.

Invariants tested:
    1. uso and solo values always stay within their valid domains
    2. Flooded cells are monotonically non-decreasing
    3. Soil migration is irreversible (SOLO_MANGUE_MIGRADO never reverts)
    4. Mangrove area (MANGUE + MANGUE_MIGRADO + MANGUE_INUNDADO) is non-decreasing
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
    USOS_INUNDADOS,
    MANGUE, MANGUE_MIGRADO, MANGUE_INUNDADO,
    SOLO_MANGUE, SOLO_MANGUE_MIGRADO, SOLO_CANAL_FLUVIAL, SOLO_OUTROS,
    VALID_SOLO,   # ← importar daqui
)

# ── paths ─────────────────────────────────────────────────────────────────────

# Input data lives in examples/data/input — no duplication in tests/fixtures
INPUT_ZIP = (
    pathlib.Path(__file__).parent.parent / "examples" / "data" / "input" / "elevacao_pol.zip"
)

# ── model parameters ──────────────────────────────────────────────────────────

TAXA_ELEVACAO = 0.05
ALTURA_MARE   = 6.0
N_STEPS       = 30

# ── valid domains ─────────────────────────────────────────────────────────────

VALID_USO  = set(range(1, 11))           # {1 … 10}

MANGUE_SET = {MANGUE, MANGUE_MIGRADO, MANGUE_INUNDADO}

# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def backend_sequence():
    """
    Run the full simulation and return a list of (uso, solo, alt) snapshots,
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
    flood     = FloodModel(backend=backend, taxa_elevacao=TAXA_ELEVACAO)
    mangrove  = MangroveModel(
        backend       = backend,
        taxa_elevacao = TAXA_ELEVACAO,
        altura_mare   = ALTURA_MARE,
    )

    orig_mangue_execute = mangrove.execute

    def patched_mangue():
        orig_mangue_execute()
        snapshots.append({
            "uso":  backend.get("uso").copy(),
            "solo": backend.get("solo").copy(),
            "alt":  backend.get("alt").copy(),
        })

    mangrove.execute = patched_mangue
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

    for band in ("uso", "alt", "solo"):
        arr = np.zeros((n_rows, n_cols), dtype=np.float32)
        arr[rows, cols] = gdf[band].astype(float).values
        backend.set(band, arr)

    return backend


# ── invariant 1: valid domains ────────────────────────────────────────────────

def test_uso_always_within_valid_domain(backend_sequence):
    """
    uso must always be in {1..10} for every valid cell at every step.
    """
    snapshots, mask = backend_sequence
    for step, snap in enumerate(snapshots, start=1):
        uso_vals = set(snap["uso"][mask].astype(int).tolist())
        invalid  = uso_vals - VALID_USO
        assert not invalid, (
            f"Step {step:02d}: uso has invalid values {invalid}. "
            f"Valid domain is {VALID_USO}."
        )


def test_solo_always_within_valid_domain(backend_sequence):
    """
    solo must always be in {0, 3, 4, 9} for every valid cell at every step.
    """
    snapshots, mask = backend_sequence
    for step, snap in enumerate(snapshots, start=1):
        solo_vals = set(snap["solo"][mask].astype(int).tolist())
        invalid   = solo_vals - VALID_SOLO
        assert not invalid, (
            f"Step {step:02d}: solo has invalid values {invalid}. "
            f"Valid domain is {VALID_SOLO}."
        )


# ── invariant 2: flooded cells are non-decreasing ────────────────────────────

def test_flooded_cells_monotonically_nondecreasing(backend_sequence):
    """
    The count of flooded cells (all USOS_INUNDADOS) must never decrease.
    Once a cell is flooded, it cannot revert (no accretion, no drainage).
    """
    snapshots, mask = backend_sequence
    counts = [
        int(np.isin(snap["uso"][mask], USOS_INUNDADOS).sum())
        for snap in snapshots
    ]
    for i in range(1, len(counts)):
        assert counts[i] >= counts[i - 1], (
            f"Flooded cell count decreased at step {i+1}: "
            f"{counts[i-1]} → {counts[i]}"
        )


# ── invariant 3: soil migration is irreversible ───────────────────────────────

def test_solo_mangue_migrado_never_reverts(backend_sequence):
    """
    Once a cell reaches SOLO_MANGUE_MIGRADO, its soil type must not
    change to any other value in subsequent steps.
    """
    snapshots, mask = backend_sequence
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1]["solo"]
        curr = snapshots[i]["solo"]

        was_migrado = (prev == SOLO_MANGUE_MIGRADO) & mask
        reverted    = was_migrado & (curr != SOLO_MANGUE_MIGRADO)

        n_reverted = int(reverted.sum())
        assert n_reverted == 0, (
            f"Step {i+1:02d}: {n_reverted} cells reverted from "
            f"SOLO_MANGUE_MIGRADO to another soil type."
        )


# ── invariant 4: mangrove area is non-decreasing ─────────────────────────────

def test_mangrove_area_nondecreasing(backend_sequence):
    """
    The total mangrove footprint (MANGUE + MANGUE_MIGRADO + MANGUE_INUNDADO)
    must be monotonically non-decreasing.

    Rationale: mangrove cells can migrate or flood, but the model has
    no mechanism to eliminate mangrove cover entirely — only to transform
    it into another mangrove state.
    """
    snapshots, mask = backend_sequence
    counts = [
        int(np.isin(snap["uso"][mask], list(MANGUE_SET)).sum())
        for snap in snapshots
    ]
    for i in range(1, len(counts)):
        assert counts[i] >= counts[i - 1], (
            f"Mangrove area decreased at step {i+1}: "
            f"{counts[i-1]} → {counts[i]} cells"
        )


# ── invariant 5: zona de influência is strictly increasing ───────────────────

def test_zona_influencia_strictly_increasing():
    """
    zonaInfluencia = altura_mare + t * taxa_elevacao is a strictly
    increasing function of time — a deterministic property of the driver.

    This test does not run the model; it verifies the formula directly.
    """
    zi_prev = ALTURA_MARE
    for t in range(1, N_STEPS + 1):
        zi = ALTURA_MARE + t * TAXA_ELEVACAO
        assert zi > zi_prev, (
            f"zonaInfluencia not strictly increasing at t={t}: "
            f"{zi_prev} → {zi}"
        )
        zi_prev = zi


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
        for band in ("uso", "solo"):
            vals = snap[band][outside]
            assert (vals == 0).all(), (
                f"Step {step:02d}: band '{band}' has non-zero values "
                f"outside the mask — {int((vals != 0).sum())} cells affected."
            )