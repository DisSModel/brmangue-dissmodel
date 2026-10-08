"""
mangrove_model.py — Mangrove Model (GeoDataFrame version)
=========================================================

Vector-based version of the canonical raster MangroveModel
(brmangue.models.raster.mangrove_model) using GeoDataFrame + SyncSpatialModel.

Same logic, different substrate:

    brmangue.models.raster.mangrove_model.py     RasterBackend (NumPy, vectorized)
    brmangue/models/vector/mangrove_model.py  ←  GeoDataFrame (libpysal, cell-by-cell)

Three processes per step — order identical to the Lua model and the
raster implementation:

    1. migrateSoils   — propagates mangrove substrate
    2. migrateUses    — propagates MIGRATED_MANGROVE land use (uses solo_past)
    3. applyAccretion — increases elevation (Alongi 2008, disabled by default)

CRITICAL NOTE: migrateUses uses solo_past — consistent with the .past
semantics used in TerraME.

Usage
-----
    from dissmodel.core import Environment
    from brmangue.models.vector.mangrove_model import MangroveModel
    import geopandas as gpd

    gdf = gpd.read_file("flood_model.shp")
    env = Environment(start_time=1, end_time=88)
    MangroveModel(gdf=gdf, sea_level_rise_rate=0.011)
    env.run()
"""
from __future__ import annotations

import geopandas as gpd
from libpysal.weights import Queen

from dissmodel.geo.vector.sync_model import SyncSpatialModel
from dissmodel.visualization import track_plot

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


@track_plot("mangrove_migrated", "green")
class MangroveModel(SyncSpatialModel):
    """
    Mangrove model implemented with DisSModel + GeoDataFrame.

    Equivalence with the raster version
    -----------------------------------
    np.isin(solo, SOIL_SOURCES)      →  solo_past.isin(SOIL_SOURCES)
    shift2d loop over DIRS_MOORE     →  loop over real GDF neighbors
    np.where(cond, new, current)     →  solo_new[idx] = SOIL_MIGRATED_MANGROVE
    solo_past (not solo_new)        →  solo_past[idx] — same .past care

    Snapshot semantics (``SyncSpatialModel``): FloodModel, registered first,
    freezes the START-of-step state in ``<col>_past``; this model reads it
    (TerraME ``cell.past``), writes over the current state, and
    re-synchronises after the step, like the raster pair.

    Parameters
    ----------
    gdf           : GeoDataFrame with columns land_use_attr, altitude_attr, soil_attr
    sea_level_rise_rate : meters/year — IPCC RCP8.5 ≈ 0.011
    tide_height   : base tidal influence height (AIM) in meters. Default: 6.0
    accretion_enabled : enables applyAccretion (Alongi 2008). Default: False
    land_use_attr      : land-use column. Default: LAND_USE
    altitude_attr      : elevation column. Default: ALTITUDE
    soil_attr     : soil type column. Default: SOIL
    """

    # constant names match the canonical raster model
    SOIL_SOURCES   = [SOIL_MANGROVE, SOIL_MIGRATED_MANGROVE, SOIL_RIVER_CHANNEL]
    MANGROVE_SOILS = [SOIL_MANGROVE, SOIL_MIGRATED_MANGROVE]
    USE_SOURCES    = [MANGROVE, MIGRATED_MANGROVE]
    USE_TARGETS    = [TERRESTRIAL_VEGETATION, BARE_SOIL]
    COEF_A, COEF_B = 1.693, 0.939   # Alongi 2008

    def setup(
        self,
        sea_level_rise_rate: float = 0.011,
        tide_height:   float = 6.0,
        accretion_enabled: bool  = False,
        land_use_attr:      str   = LAND_USE,
        altitude_attr:      str   = ALTITUDE,
        soil_attr:     str   = SOIL,
    ) -> None:
        self.sea_level_rise_rate = sea_level_rise_rate
        self.tide_height   = tide_height
        self.accretion_enabled = accretion_enabled
        self.land_use_attr      = land_use_attr
        self.altitude_attr      = altitude_attr
        self.soil_attr     = soil_attr

        # columns frozen as <col>_past (the first model to run owns the snapshot)
        self.land_use_types = [land_use_attr, altitude_attr, soil_attr]

        # metrics exposed for @track_plot / Chart — names match the raster model
        self.mangrove_migrated = 0
        self.soil_migrated     = 0

        self.create_neighborhood(strategy=Queen, silence_warnings=True)

    def pre_execute(self) -> None:
        # In a full run FloodModel (registered first) has already frozen the
        # START-of-step snapshot; taking it here would capture the post-flood
        # state. Only snapshot when running stand-alone (no snapshot yet).
        if past(self.land_use_attr) not in self.gdf.columns:
            self.synchronize()

    def execute(self) -> None:
        sea_level = self.env.now() * self.sea_level_rise_rate
        influence_zone        = self.tide_height + sea_level
        accretion_rate   = self.COEF_A / 1000.0 + self.COEF_B * sea_level

        # START-of-step state (TerraME cell.past), frozen by SyncSpatialModel.
        # All writes below go over the CURRENT state (in place, as in TerraME).
        land_use_past  = self.gdf[past(self.land_use_attr)]
        alt_past  = self.gdf[past(self.altitude_attr)]
        soil_past = self.gdf[past(self.soil_attr)]

        # ── migrateSoils ─────────────────────────────────────────────────────
        # Source: cell.past[soil] in SOIL_SOURCES
        # Target: neighbor.use  in USE_TARGETS
        #         neighbor.soil != SOIL_MIGRATED_MANGROVE
        #         neighbor.alt  <= influenceZone
        soil_sources = set(
            soil_past.index[soil_past.isin(self.SOIL_SOURCES)]
        )
        soil_new = self.gdf[self.soil_attr].copy()

        for idx in self.gdf.index:
            if land_use_past[idx] not in self.USE_TARGETS:
                continue
            if soil_past[idx] == SOIL_MIGRATED_MANGROVE:
                continue
            if alt_past[idx] > influence_zone:
                continue
            if any(n in soil_sources for n in self.neighs_id(idx)):
                soil_new[idx] = SOIL_MIGRATED_MANGROVE

        # ── migrateUses ──────────────────────────────────────────────────────
        # Source: cell.past[use] in USE_SOURCES
        # Target: neighbor.use  in USE_TARGETS
        #         neighbor.soil in MANGROVE_SOILS ← solo_past (not solo_new)
        #         neighbor.alt  <= influenceZone
        use_sources = set(
            land_use_past.index[land_use_past.isin(self.USE_SOURCES)]
        )
        land_use_new = self.gdf[self.land_use_attr].copy()

        for idx in self.gdf.index:
            if land_use_past[idx] not in self.USE_TARGETS:
                continue
            if soil_past[idx] not in self.MANGROVE_SOILS:
                continue
            if alt_past[idx] > influence_zone:
                continue
            if any(n in use_sources for n in self.neighs_id(idx)):
                land_use_new[idx] = MIGRATED_MANGROVE

        # ── applyAccretion (disabled by default — commented in original Lua) ─
        if self.accretion_enabled:
            alt_new = self.gdf[self.altitude_attr].copy()
            for idx in self.gdf.index:
                if soil_past[idx] in self.MANGROVE_SOILS:
                    if land_use_past[idx] not in FLOODED_USES:
                        alt_new[idx] += accretion_rate
            self.gdf[self.altitude_attr] = alt_new

        self.gdf[self.land_use_attr]  = land_use_new
        self.gdf[self.soil_attr] = soil_new

        # ── metrics ─────────────────────────────────────────────────────────
        self.mangrove_migrated = int((land_use_new  == MIGRATED_MANGROVE).sum())
        self.soil_migrated     = int((soil_new == SOIL_MIGRATED_MANGROVE).sum())
