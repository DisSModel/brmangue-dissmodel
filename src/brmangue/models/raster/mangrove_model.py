"""
mangrove_model.py (raster) — Mangrove Model for DisSModel
=======================================================
Faithful translation of models/mangrove.lua (brmangue-terrame; mangue.lua before the English renaming) to DisSModel + RasterBackend.
"""
from __future__ import annotations

import numpy as np
from dissmodel.geo.raster.backend import RasterBackend
from dissmodel.geo.raster.sync_model import SyncRasterModel

from brmangue.common.constants import (
    MANGROVE,
    MIGRATED_MANGROVE,
    TERRESTRIAL_VEGETATION,
    BARE_SOIL,
    FLOODED_USES,
    SOIL_MANGROVE,
    SOIL_MIGRATED_MANGROVE,
    SOIL_RIVER_CHANNEL,
)
from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL, past


class MangroveModel(SyncRasterModel):
    """
    Mangrove model (brmangue-terrame models/mangrove.lua) → DisSModel + RasterBackend.

    Uses shared snapshot semantics (auto_sync=False): the ``StepSyncModel``
    created in the executor freezes LAND_USE, ALTITUDE and SOIL in their
    ``_past`` counterparts before this model and FloodModel run, ensuring
    both read the state at the beginning of the step — equivalent to
    TerraME's ``cell.past[attr]``.

    Parameters
    ----------
    backend       : RasterBackend containing the LAND_USE, ALTITUDE and SOIL arrays
    sea_level_rise_rate : meters/year — IPCC RCP8.5 ≈ 0.011
    tide_height   : base tidal influence height (AIM) in meters. Default: 6.0
    accretion_enabled : enables sediment accretion (Alongi 2008). Default: False
    """

    SOIL_SOURCES   = [SOIL_MANGROVE, SOIL_MIGRATED_MANGROVE, SOIL_RIVER_CHANNEL]
    MANGROVE_SOILS = [SOIL_MANGROVE, SOIL_MIGRATED_MANGROVE]
    USE_SOURCES    = [MANGROVE, MIGRATED_MANGROVE]
    USE_TARGETS    = [TERRESTRIAL_VEGETATION, BARE_SOIL]
    COEF_A, COEF_B = 1.693, 0.939  # Alongi 2008

    def setup(
        self,
        backend:       RasterBackend,
        sea_level_rise_rate: float = 0.011,
        tide_height:   float = 6.0,
        accretion_enabled: bool  = False,
    ) -> None:
        super().setup(backend)
        self.land_use_types    = [LAND_USE, ALTITUDE, SOIL]
   

        self.sea_level_rise_rate     = sea_level_rise_rate
        self.tide_height       = tide_height
        self.accretion_enabled     = accretion_enabled
        self.mangrove_migrated = 0
        self.soil_migrated     = 0

    def pre_execute(self) -> None:
        # In a full run FloodModel (registered first) has already frozen the
        # START-of-step snapshot; taking it here would capture the post-flood
        # state. Only snapshot when running stand-alone (no snapshot yet).
        if past(LAND_USE) not in self.backend.arrays:
            self.synchronize()

    def execute(self) -> None:
        sea_level  = self.env.now() * self.sea_level_rise_rate
        influence_zone         = self.tide_height + sea_level
        accretion_rate    = self.COEF_A / 1000.0 + self.COEF_B * sea_level
        rows, cols = self.shape

        # mask: True = valid cell — falls back to all-True for GeoTIFF input
        mask = self.backend.arrays.get(
            "mask", np.ones((rows, cols), dtype=bool)
        ).astype(bool)

        # read shared snapshot frozen by StepSyncModel at step start
        # equivalent to TerraME's cell.past[land use / altitude / soil]
        land_use_past  = self.backend.get(past(LAND_USE))
        alt_past  = self.backend.get(past(ALTITUDE))
        soil_past = self.backend.get(past(SOIL))

        # ── soil migration ───────────────────────────────────────────────────
        is_soil_source = np.isin(soil_past, self.SOIL_SOURCES) & mask
        soil_new     = self.backend.get(SOIL).copy()  # in place over current state

        for dr, dc in self.dirs:
            source_neighbor = self.shift(is_soil_source.astype(np.int8), dr, dc) > 0
            cond = (
                source_neighbor
                & np.isin(land_use_past, self.USE_TARGETS)
                & (soil_past != SOIL_MIGRATED_MANGROVE)
                & (alt_past <= influence_zone)
                & mask
            )
            soil_new = np.where(cond, SOIL_MIGRATED_MANGROVE, soil_new)

        # ── land-use migration — uses uso_past / solo_past (TerraME .past) ──
        is_use_source = np.isin(land_use_past, self.USE_SOURCES) & mask
        land_use_new     = self.backend.get(LAND_USE).copy()   # in place over current state (TerraME)

        for dr, dc in self.dirs:
            source_neighbor = self.shift(is_use_source.astype(np.int8), dr, dc) > 0
            cond = (
                source_neighbor
                & np.isin(land_use_past, self.USE_TARGETS)
                & np.isin(soil_past, self.MANGROVE_SOILS)
                & (alt_past <= influence_zone)
                & mask
            )
            land_use_new = np.where(cond, MIGRATED_MANGROVE, land_use_new)

        # ── sediment accretion (disabled by default) ─────────────────────────
        if self.accretion_enabled:
            accretion_cond = (
                np.isin(soil_past, self.MANGROVE_SOILS)
                & ~np.isin(land_use_past, FLOODED_USES)
                & mask
            )
            alt_cur  = self.backend.get(ALTITUDE)
            alt_new = np.where(accretion_cond, alt_cur + accretion_rate, alt_cur)
            self.backend.arrays[ALTITUDE] = np.where(mask, alt_new, alt_past)

        # final guard: cells outside mask always keep their original values
        self.backend.arrays[LAND_USE]  = np.where(mask, land_use_new,  self.backend.get(LAND_USE))
        self.backend.arrays[SOIL] = np.where(mask, soil_new, self.backend.get(SOIL))

        # metrics — only count valid cells
        self.mangrove_migrated = int(np.sum((land_use_new  == MIGRATED_MANGROVE)      & mask))
        self.soil_migrated     = int(np.sum((soil_new == SOIL_MIGRATED_MANGROVE) & mask))