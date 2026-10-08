from __future__ import annotations

import geopandas as gpd
from matplotlib.colors import BoundaryNorm, ListedColormap

from dissmodel.executor     import ExperimentRecord, ModelExecutor
from dissmodel.executor.cli import run_cli
from dissmodel.io           import load_dataset, save_dataset

from brmangue.common.constants import (
    SOIL_COLORS, SOIL_LABELS,
    USE_COLORS,  USE_LABELS,
)
from brmangue.models.vector.flood_model    import FloodModel
from brmangue.models.vector.mangrove_model import MangroveModel
from brmangue.common.utils import reject_renamed_parameters
from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL

# ── colormaps ─────────────────────────────────────────────────────────────────

_vals    = sorted(USE_COLORS)
USE_CMAP = ListedColormap([USE_COLORS[k] for k in _vals])
USE_NORM = BoundaryNorm([v - 0.5 for v in _vals] + [_vals[-1] + 0.5], USE_CMAP.N)

_svals    = sorted(SOIL_COLORS)
SOIL_CMAP = ListedColormap([SOIL_COLORS[k] for k in _svals])
SOIL_NORM = BoundaryNorm([v - 0.5 for v in _svals] + [_svals[-1] + 0.5], SOIL_CMAP.N)

# Canonical column names this executor always expects after load()
CANONICAL_COLS = {LAND_USE, ALTITUDE, SOIL}


class BrmangueVectorExecutor(ModelExecutor):
    """
    Executor for the vector-based BR-MANGUE dynamics simulation.

    Couples FloodModel + MangroveModel over a shared GeoDataFrame.
    Works both as a platform executor (via API) and locally (via CLI).

    Input contract
    --------------
    After load(), the GeoDataFrame always exposes the canonical column names
    LAND_USE / ALTITUDE / SOIL (brmangue.common.constants) — regardless of the source
    file's naming convention.
    Non-canonical names are resolved via column_map before any model sees
    the data. The models receive hardcoded canonical names, not runtime params,
    which avoids the validate/run name mismatch that arises when attr_* params
    are used after column_map has already renamed the columns.
    """

    name = "brmangue_vector"

    # ── public contract ───────────────────────────────────────────────────────

    def load(self, record: ExperimentRecord) -> gpd.GeoDataFrame:
        """
        Load GeoDataFrame and apply column_map to canonical names.

        Returns a GDF whose columns always use the canonical vocabulary
        (LAND_USE / ALTITUDE / SOIL). Fills record.source.checksum.
        """
        gdf, checksum          = load_dataset(record.source.uri)
        record.source.checksum = checksum

        if record.column_map:
            # column_map: {canonical → real}  →  rename: {real → canonical}
            gdf = gdf.rename(columns={v: k for k, v in record.column_map.items()})

        record.add_log(f"Loaded GDF: {len(gdf)} features  crs={gdf.crs}")
        return gdf

    def validate(self, record: ExperimentRecord) -> None:
        """
        Stateless pre-flight checks on the record itself — no data loading.

        Catches configuration errors early (before the job enters the Dask
        queue) without paying the cost of loading the dataset twice.

        Column-level checks (missing columns after mapping) run at the start
        of run() after a single load(), where the cost is already paid.
        """
        reject_renamed_parameters(record.parameters)

        uri = record.source.uri
        if not uri:
            raise ValueError("source.uri is empty — pass 'input_dataset' in the request.")

        if record.column_map:
            unknown = set(record.column_map) - CANONICAL_COLS
            if unknown:
                raise ValueError(
                    f"column_map references unknown canonical names: {unknown}. "
                    f"Expected keys: {CANONICAL_COLS}"
                )

    def run(self, data: gpd.GeoDataFrame, record: ExperimentRecord) -> gpd.GeoDataFrame:
        """
        Validate columns, then execute the simulation.

        `data` is the GeoDataFrame returned by load(), injected by the platform.
        Models receive the canonical column names directly — no runtime
        attr_* params needed, because load() has already normalised the GDF.
        """
        from dissmodel.core import Environment

        params        = record.parameters
        end_time      = params.get("end_time",      88)
        sea_level_rise_rate = params.get("sea_level_rise_rate",  0.5)
        tide_height   = params.get("tide_height",    6.0)
        accretion_enabled = params.get("accretion_enabled",  False)

        # data injected by execute_lifecycle — no I/O here
        gdf = data

        # column-level validation (only possible after load)
        _check_columns(gdf, record)

        # ── build models ──────────────────────────────────────────────────────
        env = Environment(
            start_time = params.get("start_time", 1),
            end_time   = end_time,
        )

        FloodModel(
            gdf           = gdf,
            sea_level_rise_rate = sea_level_rise_rate,
            land_use_attr      = LAND_USE,    # always canonical after load()
            altitude_attr      = ALTITUDE,
        )
        MangroveModel(
            gdf           = gdf,
            sea_level_rise_rate = sea_level_rise_rate,
            tide_height   = tide_height,
            accretion_enabled = accretion_enabled,
            land_use_attr      = LAND_USE,    # always canonical after load()
            altitude_attr      = ALTITUDE,
            soil_attr     = SOIL,
        )

        if params.get("interactive", False):
            from dissmodel.visualization import Chart, Map
            Map(gdf=gdf, plot_params={
                "column": LAND_USE,
                "cmap":   USE_CMAP,
                "norm":   USE_NORM,
                "legend": False,
            })
            if params.get("show_chart", False):
                Chart(select={"flooded_cells", "mangrove_migrated"})

        record.add_log(f"Running steps 1 → {end_time}...")
        env.run()
        record.add_log("Simulation complete")
        # drop the <col>_past snapshot columns (internal to SyncSpatialModel)
        return gdf.drop(columns=[c for c in gdf.columns if c.endswith("_past")])

    def save(self, result: gpd.GeoDataFrame, record: ExperimentRecord) -> ExperimentRecord:
        from brmangue.common.utils import default_output_uri

        uri = (
            record.output_path
            or default_output_uri(record.experiment_id, ext="gpkg")
        )
        checksum = save_dataset(result, uri)

        record.output_path   = uri
        record.output_sha256 = checksum
        record.status        = "completed"
        record.add_log(f"Saved to {uri}")
        return record


# ── helpers ───────────────────────────────────────────────────────────────────

def _check_columns(gdf: gpd.GeoDataFrame, record: ExperimentRecord) -> None:
    """
    Verify canonical columns are present after column_map has been applied.
    Runs inside run() after a single load() — not in validate().
    """
    missing = CANONICAL_COLS - set(gdf.columns)

    if missing:
        raise ValueError(
            f"Required columns missing after column_map: {missing}\n"
            f"Dataset columns: {sorted(gdf.columns)}\n"
            f"Pass 'column_map' in the request to map non-canonical names.\n"
            f"Expected: {CANONICAL_COLS}"
        )


if __name__ == "__main__":
    run_cli(BrmangueVectorExecutor)
