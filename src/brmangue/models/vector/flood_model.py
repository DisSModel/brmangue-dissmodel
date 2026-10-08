"""
flood_model.py — Hydrological Model (GeoDataFrame version)
==========================================================

Vector-based version of the canonical raster FloodModel
(brmangue.models.raster.flood_model) using GeoDataFrame + SyncSpatialModel.

Same logic, different substrate:

    brmangue.models.raster.flood_model.py     RasterBackend (NumPy, vectorized)
    brmangue/models/vector/flood_model.py  ←  GeoDataFrame  (libpysal, cell-by-cell)

Why NOT use CellularAutomaton
------------------------------
CellularAutomaton.rule(idx) computes the new state of a cell based
on itself and its neighbors (pull model). The hydrological process
is source-oriented: flooded cells propagate flow and flooding to
their neighbors — the logic is the opposite (push model).

For this reason we inherit directly from SpatialModel and implement
execute() freely.

Usage
-----
    from dissmodel.core import Environment
    from brmangue.models.vector.flood_model import FloodModel
    import geopandas as gpd

    gdf = gpd.read_file("flood_model.shp")
    env = Environment(start_time=1, end_time=88)
    FloodModel(gdf=gdf, sea_level_rise_rate=0.011)
    env.run()
"""
from __future__ import annotations

import geopandas as gpd
from libpysal.weights import Queen

from dissmodel.geo.vector.sync_model import SyncSpatialModel
from dissmodel.visualization import track_plot

from brmangue.common.constants import (
    FLOODED_USES,
    FLOODING_RULES,
    SEA,
)
from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL, past

@track_plot("flooded_cells", "blue")
class FloodModel(SyncSpatialModel):
    """
    Hydrological model implemented with DisSModel + GeoDataFrame.

    Equivalence with the raster version
    -----------------------------------
    RasterBackend.shift2d()          →  neighs_id(idx) / neighbor_values()
    np.isin(land_use, FLOODED_USES) →  land_use_past.isin(FLOODED_USES)
    loop over DIRS_MOORE             →  loop over real GDF neighbors only
                                        (off-grid / off-mask positions are
                                        not neighbors, as in TerraME)
    vectorized over full grid        →  cell-by-cell loop (slower,
                                        but faithful to real geometry)

    Snapshot semantics (``SyncSpatialModel``, the vector twin of the raster
    ``SyncRasterModel``): this model runs FIRST in each step and owns the
    start-of-step snapshot of every state column (``<col>_past``; TerraME:
    ``cs:synchronize()`` at the end of the previous step). It does not
    re-snapshot after its own ``execute``; MangroveModel reads the same
    snapshot and re-synchronises once both models have run.

    Parameters
    ----------
    gdf           : GeoDataFrame with columns land_use_attr and altitude_attr
    sea_level_rise_rate : meters/year — IPCC RCP8.5 ≈ 0.011
    land_use_attr      : land-use column. Default: LAND_USE
    altitude_attr      : elevation column. Default: ALTITUDE
    """

    def setup(
        self,
        sea_level_rise_rate: float = 0.011,
        land_use_attr:      str   = LAND_USE,
        altitude_attr:      str   = ALTITUDE,
    ) -> None:
        self.sea_level_rise_rate = sea_level_rise_rate
        self.land_use_attr      = land_use_attr
        self.altitude_attr      = altitude_attr

        # columns frozen as <col>_past at the start of every step
        self.land_use_types = [land_use_attr, altitude_attr] + (
            [SOIL] if SOIL in self.gdf.columns else []
        )

        # metrics exposed for @track_plot / Chart — names match the raster model
        self.flooded_cells     = 0
        self.newly_flooded     = 0
        self.current_sea_level = 0.0

        # Queen = Moore neighborhood (8 directions) for regular grids
        # silence_warnings suppresses island warnings (cells without neighbors)
        self.create_neighborhood(strategy=Queen, silence_warnings=True)

    def post_execute(self) -> None:
        # No snapshot here: MangroveModel still has to read the START-of-step
        # state. It re-synchronises all columns once both models have run.
        pass

    def execute(self) -> None:
        sea_level = self.env.now() * self.sea_level_rise_rate

        # START-of-step state (TerraME cell.past), frozen by SyncSpatialModel
        land_use_past = self.gdf[past(self.land_use_attr)]
        alt_past = self.gdf[past(self.altitude_attr)]

        # ── sources: isSeaOrFlooded(land use) and alt >= 0 ─────────────────────────
        sources = set(
            land_use_past.index[
                land_use_past.isin(FLOODED_USES) & (alt_past >= 0)
            ]
        )

        # ── A. Elevation — flow diffusion (relative condition) ────────────────
        # Lua: if neighbor.past[alt] <= currentAlt: neigh[alt] += flow
        alt_new = alt_past.copy()

        for idx in sources:
            alt_current = alt_past[idx]
            neighbors  = self.neighs_id(idx)

            lower_neighbors = 1 + sum(
                1 for n in neighbors if alt_past[n] <= alt_current
            )
            flux = self.sea_level_rise_rate / lower_neighbors

            alt_new[idx] += flux
            for n in neighbors:
                if alt_past[n] <= alt_current:
                    alt_new[n] += flux

        self.gdf[self.altitude_attr] = alt_new

        # ── B. Flooding — absolute elevation threshold ───────────────────────
        # Lua: if neighbor.past[alt] <= seaLevel and not isSeaOrFlooded(neigh):
        #          applyFlooding(neighbor)
        # Uses alt_past — faithful to TerraME .past semantics
        land_use_new = land_use_past.copy()

        for idx in self.gdf.index:
            land_use_current = land_use_past[idx]
            if land_use_current not in FLOODING_RULES:
                continue
            if alt_past[idx] > sea_level:
                continue
            if any(n in sources for n in self.neighs_id(idx)):
                land_use_new[idx] = FLOODING_RULES[land_use_current]

        self.gdf[self.land_use_attr] = land_use_new

        # ── metrics ──────────────────────────────────────────────────────────
        flooded = land_use_new.isin(FLOODED_USES) & (land_use_new != SEA)
        newly = land_use_new.isin(FLOODED_USES) & ~land_use_past.isin(FLOODED_USES)

        self.flooded_cells     = int(flooded.sum())
        self.newly_flooded     = int(newly.sum())
        self.current_sea_level = round(sea_level, 4)
