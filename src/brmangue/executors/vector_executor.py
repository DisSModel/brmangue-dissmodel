from __future__ import annotations

import geopandas as gpd
from matplotlib.colors import BoundaryNorm, ListedColormap

from dissmodel.executor     import ExperimentRecord, ModelExecutor
from dissmodel.executor.cli import run_cli
from dissmodel.io           import load_dataset, save_dataset

from brmangue.common.constants import (
    SOLO_COLORS, SOLO_LABELS,
    USO_COLORS,  USO_LABELS,
)
from brmangue.models.vector.flood_model    import FloodModel
from brmangue.models.vector.mangrove_model import MangroveModel

# ── colormaps ─────────────────────────────────────────────────────────────────

_vals    = sorted(USO_COLORS)
USO_CMAP = ListedColormap([USO_COLORS[k] for k in _vals])
USO_NORM = BoundaryNorm([v - 0.5 for v in _vals] + [_vals[-1] + 0.5], USO_CMAP.N)

_svals    = sorted(SOLO_COLORS)
SOLO_CMAP = ListedColormap([SOLO_COLORS[k] for k in _svals])
SOLO_NORM = BoundaryNorm([v - 0.5 for v in _svals] + [_svals[-1] + 0.5], SOLO_CMAP.N)

# Canonical column names this executor always expects after load()
CANONICAL_COLS = {"uso", "alt", "solo"}


class BrmangueVectorExecutor(ModelExecutor):
    """
    Executor for the vector-based BR-MANGUE dynamics simulation.

    Couples FloodModel + MangroveModel over a shared GeoDataFrame.
    Works both as a platform executor (via API) and locally (via CLI).

    Input contract
    --------------
    After load(), the GeoDataFrame always exposes the canonical column names
    "uso", "alt", "solo" — regardless of the source file's naming convention.
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
        ("uso", "alt", "solo"). Fills record.source.checksum.
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
        taxa_elevacao = params.get("taxa_elevacao",  0.5)
        altura_mare   = params.get("altura_mare",    6.0)
        acrecao_ativa = params.get("acrecao_ativa",  False)

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
            taxa_elevacao = taxa_elevacao,
            attr_uso      = "uso",    # always canonical after load()
            attr_alt      = "alt",
        )
        MangroveModel(
            gdf           = gdf,
            taxa_elevacao = taxa_elevacao,
            altura_mare   = altura_mare,
            acrecao_ativa = acrecao_ativa,
            attr_uso      = "uso",    # always canonical after load()
            attr_alt      = "alt",
            attr_solo     = "solo",
        )

        if params.get("interactive", False):
            from dissmodel.visualization import Chart, Map
            Map(gdf=gdf, plot_params={
                "column": "uso",
                "cmap":   USO_CMAP,
                "norm":   USO_NORM,
                "legend": False,
            })
            if params.get("show_chart", False):
                Chart(select={"flooded_cells", "mangrove_migrated"})

        record.add_log(f"Running steps 1 → {end_time}...")
        env.run()
        record.add_log("Simulation complete")
        return gdf

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
