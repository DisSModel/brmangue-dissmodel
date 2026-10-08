"""
flood_model.py (raster) — Hydrological Model for DisSModel
========================================================
Faithful translation of models/flood.lua (brmangue-terrame; hidro.lua before the English renaming) to DisSModel + RasterBackend.
"""
from __future__ import annotations

import numpy as np
from dissmodel.geo.raster.backend import RasterBackend
from dissmodel.geo.raster.sync_model import SyncRasterModel

from brmangue.common.constants import (
    FLOODED_USES,
    FLOODING_RULES,
    SEA,
)
from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL, past


class FloodModel(SyncRasterModel):
    """
    Hydrological model (brmangue-terrame models/flood.lua) → DisSModel + RasterBackend.

    Shared snapshot semantics: this model (registered first) takes the
    start-of-step snapshot in ``pre_execute`` and does NOT re-snapshot after
    its own ``execute``; MangroveModel re-snapshots after the full step. Both
    therefore read the state at the beginning of the step — equivalent to
    TerraME's ``cell.past[attr]`` — while writing over the current state.

    Parameters
    ----------
    backend       : RasterBackend containing the LAND_USE and ALTITUDE arrays
    sea_level_rise_rate : meters/year — IPCC RCP8.5 ≈ 0.011
    """

    def setup(
        self,
        backend:       RasterBackend,
        sea_level_rise_rate: float = 0.011,
    ) -> None:
        super().setup(backend)
        # FloodModel runs FIRST in each step and owns the start-of-step
        # snapshot of every state array (TerraME: cs:synchronize() at the end
        # of the previous step). MangroveModel reads the same snapshot.
        self.land_use_types    = [LAND_USE, ALTITUDE] + (
            [SOIL] if SOIL in backend.arrays else []
        )

        self.sea_level_rise_rate     = sea_level_rise_rate
        self.flooded_cells     = 0
        self.newly_flooded     = 0
        self.current_sea_level = 0.0

    def post_execute(self) -> None:
        # No snapshot here: MangroveModel still has to read the START-of-step
        # state. It re-synchronises all arrays once both models have run.
        pass

    def execute(self) -> None:
        sea_level  = self.env.now() * self.sea_level_rise_rate
        rows, cols = self.shape

        # mask: True = valid cell (covered by a polygon)
        # falls back to all-True if backend was loaded from GeoTIFF (no mask band)
        mask = self.backend.arrays.get(
            "mask", np.ones((rows, cols), dtype=bool)
        ).astype(bool)

        # read shared snapshot frozen by StepSyncModel at step start
        # equivalent to TerraME's cell.past[land use] / cell.past[altitude]
        land_use_past = self.backend.get(past(LAND_USE))
        alt_past = self.backend.get(past(ALTITUDE))

        # source cells: already flooded or sea — only within valid area
        is_source = np.isin(land_use_past, FLOODED_USES) & (alt_past >= 0) & mask

        # Neighbour count must only include cells that exist in the cellular
        # space (TerraME neighbourhoods never contain cells outside the polygon
        # mask). Padding cells hold alt=0, so without ``& neighbor_mask`` they would
        # count as "lower neighbours" and dilute the flux along the borders.
        lower_neighbors = np.ones((rows, cols), dtype=float)
        for dr, dc in self.dirs:
            neighbor_mask = self.shift(mask.astype(float), dr, dc) > 0
            lower_neighbors += (
                neighbor_mask & (self.shift(alt_past, dr, dc) <= alt_past)
            ).astype(float)

        flux     = np.where(is_source, self.sea_level_rise_rate / lower_neighbors, 0.0)
        delta_alt = flux.copy()
        land_use_new  = land_use_past.copy()

        for dr, dc in self.dirs:
            source_neighbor = self.shift(is_source.astype(float), dr, dc) > 0
            alt_neighbor   = self.shift(alt_past, dr, dc)
            neighbor_flux = self.shift(flux, dr, dc)

            # 1. elevation update — relative condition
            delta_alt += np.where(
                source_neighbor & (alt_past <= alt_neighbor), neighbor_flux, 0.0
            )

            # 2. flooding — absolute elevation threshold
            for dry_use, flooded_use in FLOODING_RULES.items():
                can_flood = (
                    source_neighbor
                    & (land_use_past == dry_use)
                    & (alt_past <= sea_level)
                    & mask          # never flood outside valid area
                )
                land_use_new = np.where(can_flood, flooded_use, land_use_new)

        # final guard: cells outside mask always keep their original values
        alt_new = alt_past + delta_alt
        self.backend.arrays[ALTITUDE] = np.where(mask, alt_new, alt_past)
        self.backend.arrays[LAND_USE] = np.where(mask, land_use_new, land_use_past)

        # metrics
        flooded = np.isin(land_use_new, FLOODED_USES) & (land_use_new != SEA) & mask
        newly = (
            np.isin(land_use_new, FLOODED_USES)
            & ~np.isin(land_use_past, FLOODED_USES)
            & mask
        )

        self.flooded_cells     = int(np.sum(flooded))
        self.newly_flooded     = int(np.sum(newly))
        self.current_sea_level = round(sea_level, 4)