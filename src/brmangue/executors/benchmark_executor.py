from __future__ import annotations

import io
import time

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from dissmodel.core               import Environment
from dissmodel.executor           import ExperimentRecord, ModelExecutor
from dissmodel.executor.cli       import run_cli
from dissmodel.geo.raster.backend import RasterBackend
from dissmodel.io                 import load_dataset
from dissmodel.io._utils          import write_bytes, write_text
from dissmodel.executor.config    import settings

from brmangue.models.raster.flood_model    import FloodModel    as RasterFlood
from brmangue.models.raster.mangrove_model import MangroveModel as RasterMangue
from brmangue.models.vector.flood_model    import FloodModel    as VectorFlood
from brmangue.models.vector.mangrove_model import MangroveModel as VectorMangue

CANONICAL_COLS = {"uso", "alt", "solo"}


class BrmangueBenchmarkExecutor(ModelExecutor):
    """
    Meta-executor that runs both Vector and Raster models against the same
    input to validate mathematical equivalence across substrates.

    The raster models are the canonical, TerraME-validated implementation
    (brmangue.models.raster); the vector models (brmangue.models.vector) are expected to
    reproduce their behavior within tolerance.

    Input contract
    --------------
    Expects a vector dataset with canonical columns "uso", "alt", "solo"
    plus integer grid indices "row" and "col" for 1:1 raster alignment.
    The mock raster bypasses geographic projection — it validates model
    math, not spatial accuracy.

    Output
    ------
    Two artifacts written to output_path (local dir or s3://):
        scatter.png  — per-band vector vs raster scatter plots
        report.md    — runtime and accuracy metrics in Markdown
    Both checksums are registered in record.artifacts.
    """

    name = "brmangue_benchmark"

    # ── public contract ───────────────────────────────────────────────────────

    def load(self, record: ExperimentRecord) -> gpd.GeoDataFrame:
        """
        Load and normalise the vector dataset.
        Returns a GDF with canonical column names guaranteed.
        """
        gdf, checksum = load_dataset(record.source.uri, fmt="vector")
        record.source.checksum = checksum

        if record.column_map:
            gdf = gdf.rename(columns={v: k for k, v in record.column_map.items()})

        record.add_log(f"Loaded GDF: {len(gdf):,} features  crs={gdf.crs}")
        return gdf

    def validate(self, record: ExperimentRecord) -> None:
        """
        Stateless pre-flight checks — no data loading.

        Column-level checks ("uso"/"alt"/"solo" and "row"/"col") run at
        the start of run() after a single load(), where the cost is paid once.
        """
        if not record.source.uri:
            raise ValueError(
                "source.uri is empty — pass 'input_dataset' in the request."
            )

        if record.column_map:
            unknown = set(record.column_map) - CANONICAL_COLS
            if unknown:
                raise ValueError(
                    f"column_map references unknown canonical names: {unknown}. "
                    f"Expected keys: {CANONICAL_COLS}"
                )

    def run(self, data: gpd.GeoDataFrame, record: ExperimentRecord) -> dict:
        """
        Validate columns, then execute both Vector and Raster models.

        `data` is the GeoDataFrame returned by load(), injected by the platform.
        No I/O happens here.
        """
        params        = record.parameters
        n_steps       = params.get("end_time",      10)
        taxa_elevacao = params.get("taxa_elevacao",  0.011)
        altura_mare   = params.get("altura_mare",    6.0)
        tolerance     = params.get("tolerance",      0.05)

        # data injected by execute_lifecycle — no I/O here
        gdf_orig = data

        # column-level validation (only possible after load)
        _check_columns(gdf_orig, record)

        # ── vector run ────────────────────────────────────────────────────────
        record.add_log(f"Running Vector Model ({n_steps} steps)...")
        gdf_result = gdf_orig.copy()
        env_vec    = Environment(start_time=1, end_time=n_steps)

        VectorFlood(
            gdf           = gdf_result,
            taxa_elevacao = taxa_elevacao,
            attr_uso      = "uso",
            attr_alt      = "alt",
        )
        VectorMangue(
            gdf           = gdf_result,
            taxa_elevacao = taxa_elevacao,
            altura_mare   = altura_mare,
            attr_uso      = "uso",
            attr_alt      = "alt",
            attr_solo     = "solo",
        )

        t0     = time.perf_counter()
        env_vec.run()
        vec_ms = (time.perf_counter() - t0) * 1000 / n_steps
        record.add_log(f"Vector done: {vec_ms:.1f} ms/step")

        # ── raster run (mock 1:1 alignment) ───────────────────────────────────
        record.add_log(f"Running Raster Model ({n_steps} steps)...")
        backend, rows, cols = _build_mock_raster(gdf_orig)
        env_ras             = Environment(start_time=1, end_time=n_steps)

        RasterFlood(
            backend       = backend,
            taxa_elevacao = taxa_elevacao,
        )
        RasterMangue(
            backend       = backend,
            taxa_elevacao = taxa_elevacao,
            altura_mare   = altura_mare,
        )

        t0     = time.perf_counter()
        env_ras.run()
        ras_ms = (time.perf_counter() - t0) * 1000 / n_steps
        record.add_log(f"Raster done: {ras_ms:.1f} ms/step")

        # ── metrics ───────────────────────────────────────────────────────────
        record.add_log("Calculating metrics...")
        band_metrics = {}
        for band in sorted(CANONICAL_COLS):
            if band not in gdf_result.columns:
                continue
            vec_vals = gdf_result[band].values.astype(float)
            ras_vals = backend.get(band)[rows, cols].astype(float)
            diff     = np.abs(vec_vals - ras_vals)
            band_metrics[band] = {
                "match_pct": float((diff <= tolerance).mean() * 100),
                "mae":       float(diff.mean()),
                "rmse":      float(np.sqrt((diff ** 2).mean())),
                "max_err":   float(diff.max()),
                "n_cells":   len(vec_vals),
            }
            m = band_metrics[band]
            record.add_log(
                f"  {band}: match={m['match_pct']:.2f}%  "
                f"MAE={m['mae']:.6f}  RMSE={m['rmse']:.6f}"
            )

        # ── scatter plots (in-memory) ─────────────────────────────────────────
        record.add_log("Generating artifacts...")
        n_bands   = len(band_metrics)
        fig, axes = plt.subplots(1, n_bands, figsize=(6 * n_bands, 5))
        if n_bands == 1:
            axes = [axes]

        for ax, (band, m) in zip(axes, band_metrics.items()):
            vec_vals = gdf_result[band].values.astype(float)
            ras_vals = backend.get(band)[rows, cols].astype(float)
            ax.scatter(vec_vals, ras_vals, alpha=0.4, s=6, color="steelblue")
            lim = max(float(np.max(vec_vals)), float(np.max(ras_vals))) * 1.05
            ax.plot([0, lim], [0, lim], "r--", lw=1)
            ax.set_xlabel(f"Vector {band}")
            ax.set_ylabel(f"Raster {band}")
            ax.set_title(f"{band} — Vector vs Raster")
            ax.text(
                0.05, 0.88,
                f"Match: {m['match_pct']:.1f}%\nMAE: {m['mae']:.5f}",
                transform = ax.transAxes,
                fontsize  = 8,
                bbox      = dict(facecolor="wheat", alpha=0.5),
            )

        plt.suptitle(f"BR-MANGUE Vector vs Raster — {n_steps} steps", fontsize=11)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150)
        plt.close()

        return {
            "plot_buf":   buf,
            "report_str": _build_markdown(n_steps, tolerance, vec_ms, ras_ms, band_metrics),
            "metrics":    band_metrics,
        }

    def save(self, result: dict, record: ExperimentRecord) -> ExperimentRecord:
        """
        Write scatter.png and report.md to output_path.

        output_path resolved in order:
          1. platform runner  → sets record.output_path before calling save()
          2. CLI --output arg → passed via record.output_path
          3. settings fallback → settings.default_output_base (never hardcoded here)
        """
        base_uri = (
            record.output_path
            or f"{settings.default_output_base}/experiments/{record.experiment_id}/benchmark"
        )

        record.add_artifact(
            "plot",
            write_bytes(
                result["plot_buf"],
                f"{base_uri}/scatter.png",
                content_type = "image/png",
            ),
        )
        record.add_artifact(
            "report",
            write_text(
                result["report_str"],
                f"{base_uri}/report.md",
                content_type = "text/markdown",
            ),
        )

        record.output_path = base_uri
        record.metrics     = result["metrics"]
        record.status      = "completed"
        record.add_log(f"Saved scatter.png → {base_uri}/scatter.png")
        record.add_log(f"Saved report.md   → {base_uri}/report.md")
        return record


# ── helpers ───────────────────────────────────────────────────────────────────

def _check_columns(gdf: gpd.GeoDataFrame, record: ExperimentRecord) -> None:
    """
    Verify canonical columns and grid indices after load().
    Runs inside run() — not in validate().
    """
    missing_canonical = CANONICAL_COLS - set(gdf.columns)
    if missing_canonical:
        raise ValueError(
            f"Required columns missing after column_map: {missing_canonical}\n"
            f"Dataset columns: {sorted(gdf.columns)}\n"
            f"Pass 'column_map' in the request to map non-canonical names."
        )

    missing_index = {"row", "col"} - set(gdf.columns)
    if missing_index:
        raise ValueError(
            f"Columns 'row' and 'col' are required for mock raster alignment "
            f"but are missing: {missing_index}\n"
            f"These must be integer grid indices present in the dataset."
        )


def _build_mock_raster(
    gdf: gpd.GeoDataFrame,
) -> tuple[RasterBackend, np.ndarray, np.ndarray]:
    """
    Build a RasterBackend aligned 1:1 with the GDF using row/col indices.
    Bypasses geographic projection — validates model math, not spatial accuracy.
    """
    rows   = gdf["row"].astype(int).values
    cols   = gdf["col"].astype(int).values
    n_rows = int(rows.max()) + 1
    n_cols = int(cols.max()) + 1

    backend          = RasterBackend(shape=(n_rows, n_cols))
    mask             = np.zeros((n_rows, n_cols), dtype=bool)
    mask[rows, cols] = True
    backend.set("mask", mask)

    for band in CANONICAL_COLS:
        if band in gdf.columns:
            arr             = np.zeros((n_rows, n_cols), dtype=np.float32)
            arr[rows, cols] = gdf[band].astype(float).values
            backend.set(band, arr)

    return backend, rows, cols


def _build_markdown(
    n_steps:   int,
    tolerance: float,
    vec_ms:    float,
    ras_ms:    float,
    metrics:   dict,
) -> str:
    speedup = vec_ms / ras_ms if ras_ms > 0 else float("inf")
    lines   = [
        "# BR-MANGUE Vector vs Raster Benchmark Report\n\n",
        f"**Steps:** {n_steps} | **Tolerance:** {tolerance}\n\n",
        "## Runtime\n\n",
        "| Substrate | ms/step | Speedup |\n|---|---|---|\n",
        f"| Vector | {vec_ms:.1f} | 1.0× |\n",
        f"| Raster | {ras_ms:.1f} | {speedup:.1f}× |\n\n",
        "## Accuracy\n\n",
        "| Band | Match % | MAE | RMSE | Max err | N cells |\n",
        "|---|---|---|---|---|---|\n",
    ]
    for band, m in metrics.items():
        lines.append(
            f"| {band} | {m['match_pct']:.2f}% | {m['mae']:.6f} | "
            f"{m['rmse']:.6f} | {m['max_err']:.6f} | {m['n_cells']} |\n"
        )
    return "".join(lines)


if __name__ == "__main__":
    run_cli(BrmangueBenchmarkExecutor)
