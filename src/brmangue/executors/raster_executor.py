from __future__ import annotations

from dissmodel.executor     import ExperimentRecord, ModelExecutor
from dissmodel.executor.cli import run_cli
from dissmodel.io           import load_dataset, save_dataset

from brmangue.common.constants import (
    SEA, TIFF_BANDS, CRS,
    USE_COLORS, USE_LABELS,
    SOIL_COLORS, SOIL_LABELS,
    SOIL_RIVERBED, 
)
from brmangue.models.raster.flood_model    import FloodModel
from brmangue.models.raster.mangrove_model import MangroveModel
from brmangue.common.utils import reject_renamed_parameters
from brmangue.common.constants import ALTITUDE, LAND_USE, SOIL

# ── visualization config ──────────────────────────────────────────────────────

BAND_CONFIG: dict[str, dict] = {
    LAND_USE:  dict(color_map=USE_COLORS, labels=USE_LABELS, title="Land Use"),
    SOIL: dict(color_map=SOIL_COLORS, labels=SOIL_LABELS, title="Soil"),
    ALTITUDE:  dict(
        cmap           = "terrain",
        colorbar_label = "Elevation (m)",
        mask_band      = LAND_USE,
        mask_value     = SEA,
        title          = "Elevation",
    ),
}

SHAPEFILE_DEFAULTS: dict[str, int | float] = {
    LAND_USE:  5,
    ALTITUDE:  0.0,
    SOIL: SOIL_RIVERBED,     
}

# Canonical band names this executor always expects after load()
CANONICAL_BANDS = {LAND_USE, ALTITUDE, SOIL}


class BrmangueRasterExecutor(ModelExecutor):
    """
    Executor for the raster-based BR-MANGUE dynamics simulation.

    Accepts GeoTIFF (resume) or vector (new simulation) as input.
    Couples FloodModel + MangroveModel over a shared RasterBackend.
    Works both as a platform executor (via API) and locally (via CLI).

    Input contract
    --------------
    After load(), the RasterBackend always exposes the canonical band names
    LAND_USE / ALTITUDE / SOIL (brmangue.common.constants) — regardless of the source
    file's naming convention.
    Non-canonical names are resolved via band_map (tiff) or column_map (vector)
    before any model sees the data.
    """

    name = "brmangue_raster"

    # ── public contract ───────────────────────────────────────────────────────

    @staticmethod
    def from_cube(backend: RasterBackend) -> tuple:
        """
        Adapts a RasterBackend from DisSCube to the internal format
        expected by BrmangueRasterExecutor (backend, meta, start_time).
        """
        meta = {
            "crs": backend.crs,
            "transform": backend.transform,
            "tags": {}
        }
        start_time = 1
        return backend, meta, start_time

    def load(self, record: ExperimentRecord):
        """
        Load RasterBackend from GeoTIFF or rasterize a vector file.

        Returns (backend, meta, start_time). Band names in the returned backend
        are always canonical (LAND_USE / ALTITUDE / SOIL).
        """
        from dissmodel.io.convert import vector_to_raster_backend

        params = record.parameters
        uri    = record.source.uri
        fmt    = record.input_format

        if fmt == "auto":
            fmt = _detect_format(uri)

        if fmt == "tiff":
            (backend, meta), checksum = load_dataset(
                uri, fmt="raster", band_spec=TIFF_BANDS
            )
            record.source.checksum = checksum

            for canonical, real in record.band_map.items():
                backend.rename_band(real, canonical)

            tags  = meta.get("tags", {})
            start = int(tags.get("passo", 0)) + 1   # "passo" (step): tag name in existing GeoTIFFs
            record.add_log(
                f"Loaded GeoTIFF: shape={backend.shape} "
                f"start={start} crs={meta.get('crs')}"
            )

        else:
            gdf, checksum = load_dataset(uri, fmt="vector")
            record.source.checksum = checksum

            if record.column_map:
                gdf = gdf.rename(columns={v: k for k, v in record.column_map.items()})

            resolution = params.get("resolution", 100.0)
            crs        = params.get("crs", CRS)

            backend = vector_to_raster_backend(
                source      = gdf,
                resolution  = resolution,
                attrs       = SHAPEFILE_DEFAULTS,
                crs         = crs,
                all_touched = False,
                nodata      = 0,
            )
            meta  = {"crs": crs, "transform": None, "tags": {}}
            start = 1
            record.add_log(
                f"Rasterized vector: shape={backend.shape} "
                f"resolution={resolution}m"
            )

        return backend, meta, start

    def validate(self, record: ExperimentRecord) -> None:
        """
        Stateless pre-flight checks on the record itself — no data loading.

        Catches configuration errors early (before the job enters the Dask
        queue) without paying the cost of loading the dataset twice.

        Band-level checks (missing bands, elevation range) run at the start
        of run() after a single load(), where the cost is already paid.
        """
        reject_renamed_parameters(record.parameters)

        uri = record.source.uri
        if not uri:
            raise ValueError("source.uri is empty — pass 'input_dataset' in the request.")

        fmt = record.input_format
        if fmt not in {"tiff", "vector", "auto"}:
            raise ValueError(
                f"input_format={fmt!r} is not valid. "
                f"Use 'tiff', 'vector', or 'auto'."
            )

        if fmt == "tiff" and record.band_map:
            unknown = set(record.band_map) - CANONICAL_BANDS
            if unknown:
                raise ValueError(
                    f"band_map references unknown canonical names: {unknown}. "
                    f"Expected keys: {CANONICAL_BANDS}"
                )

        if fmt in {"vector", "auto"} and record.column_map:
            unknown = set(record.column_map) - CANONICAL_BANDS
            if unknown:
                raise ValueError(
                    f"column_map references unknown canonical names: {unknown}. "
                    f"Expected keys: {CANONICAL_BANDS}"
                )

    def run(self, data, record: ExperimentRecord):
        """
        Validate bands, then execute the simulation.

        `data` is the (backend, meta, start) tuple returned by load(),
        injected by the platform. No I/O happens here.
        """
        from dissmodel.core import Environment
        from dissmodel.visualization.raster_map import RasterMap

        params        = record.parameters
        end_time      = params.get("end_time",      88)
        sea_level_rise_rate = params.get("sea_level_rise_rate",  0.5)
        tide_height   = params.get("tide_height",    6.0)
        accretion_enabled = params.get("accretion_enabled",  False)
        bands         = params.get("bands",          [LAND_USE])

        # data injected by execute_lifecycle — no I/O here
        backend, meta, start = data

        # band-level validation (only possible after load)
        _check_bands(backend, record)

        # ── build models ──────────────────────────────────────────────────────
        env = Environment(start_time=start, end_time=end_time)

        FloodModel(
            backend       = backend,
            sea_level_rise_rate = sea_level_rise_rate,
        )
        MangroveModel(
            backend       = backend,
            sea_level_rise_rate = sea_level_rise_rate,
            tide_height   = tide_height,
            accretion_enabled = accretion_enabled,
        )

        if params.get("interactive", False):
            for band in bands:
                if band not in BAND_CONFIG:
                    record.add_log(
                        f"Warning: band '{band}' has no visual config — using viridis"
                    )
                RasterMap(
                    backend     = backend,
                    band        = band,
                    save_frames = False,
                    **BAND_CONFIG.get(band, {}),
                )

        record.add_log(f"Running steps {start} → {end_time}...")
        env.run()
        record.add_log("Simulation complete")

        return backend, meta

    def save(self, result, record: ExperimentRecord) -> ExperimentRecord:
        from brmangue.common.utils import default_output_uri
        from dissmodel.io.raster import save_geotiff
        
        backend, meta = result

        uri = (
            record.output_path
            or default_output_uri(record.experiment_id, ext="tif")
        )
        checksum = save_geotiff(
            (backend, meta), uri,
            band_spec = TIFF_BANDS,
            crs       = meta.get("crs") or CRS,
            transform = meta.get("transform"),
        )

        record.output_path   = uri
        record.output_sha256 = checksum
        record.status        = "completed"
        record.add_log(f"Saved to {uri}")
        return record


# ── helpers ───────────────────────────────────────────────────────────────────

def _check_bands(backend, record: ExperimentRecord) -> None:
    """
    Verify canonical bands are present and elevation values are plausible.
    Runs inside run() after a single load() — not in validate().
    """
    actual  = set(backend.band_names())
    missing = CANONICAL_BANDS - actual

    if missing:
        hint = "band_map" if record.input_format == "tiff" else "column_map"
        raise ValueError(
            f"Bands missing after mapping: {missing}\n"
            f"Pass '{hint}' in the request to map non-canonical names.\n"
            f"Available bands: {sorted(actual)}"
        )

    alt = backend.get(ALTITUDE)
    if alt.min() < -500 or alt.max() > 9000:
        raise ValueError(
            f"Band '{ALTITUDE}' has implausible values: [{alt.min():.1f}, {alt.max():.1f}]. "
            f"Expected elevation in metres. Check band_map."
        )


def _detect_format(uri: str) -> str:
    """Infer input format from URI extension."""
    import pathlib
    import zipfile

    ext = pathlib.Path(uri.split("?")[0]).suffix.lower()

    if ext in {".tif", ".tiff"}:
        return "tiff"

    if ext == ".zip":
        try:
            with zipfile.ZipFile(uri) as zf:
                names = zf.namelist()
            for name in names:
                e = pathlib.Path(name).suffix.lower()
                if e in {".tif", ".tiff"}:
                    return "tiff"
                if e in {".shp", ".geojson", ".gpkg"}:
                    return "vector"
        except Exception:
            pass

    return "vector"


if __name__ == "__main__":
    run_cli(BrmangueRasterExecutor)
