# examples/prepare_raster.py
"""
Converts a vector shapefile to a GeoTIFF ready for BrmangueRasterExecutor.
Run once as a preprocessing step — save the output and reuse it.

Usage:
    python prepare_raster.py data/mangue_grid.shp \
      --resolution 100 --crs EPSG:31984 --output data/mangue_grid.tif
"""
from __future__ import annotations

import argparse
import pathlib

import geopandas as gpd

from dissmodel.io.convert import vector_to_raster_backend
from dissmodel.io.raster  import save_geotiff

from brmangue.common.constants import TIFF_BANDS, CRS

SHAPEFILE_DEFAULTS: dict[str, int | float] = {
    "uso":  5,
    "alt":  0.0,
    "solo": 1,
}



def prepare(shp: str, resolution: float, crs: str, output: str) -> None:
    shp_path = pathlib.Path(shp)
    out_path = pathlib.Path(output) if output else \
               shp_path.with_suffix(".tif")

    print(f"Loading {shp_path}...")
    gdf = gpd.read_file(str(shp_path))

    # Preenche os valores vazios (NaN) do vetor com os valores padrão
    for col, default_val in SHAPEFILE_DEFAULTS.items():
        if col in gdf.columns:
            gdf[col] = gdf[col].fillna(default_val)

    print(f"  {len(gdf):,} features  crs={gdf.crs}")

    print(f"Rasterizing at {resolution}m resolution...")
    backend = vector_to_raster_backend(
        source      = gdf,
        resolution  = resolution,
        attrs       = SHAPEFILE_DEFAULTS,
        crs         = crs,
        all_touched = False,
        nodata      = 0,
    )
    
    valid = int(backend.get("mask").sum()) if "mask" in backend.band_names() else "?"
    print(f"  shape={backend.shape}  valid cells={valid}")

    print(f"Saving to {out_path}...")
    checksum = save_geotiff(
        (backend, {"crs": crs, "transform": backend.transform}),
        str(out_path),
        band_spec = TIFF_BANDS,
        crs       = crs,
    )
    print(f"  sha256: {checksum[:16]}...")
    print(f"\nDone: {out_path}")
    print("Use with --format tiff in main_raster.py")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Convert shapefile to GeoTIFF for BrmangueRasterExecutor")
    p.add_argument("shp",                            help="Input shapefile or zip")
    p.add_argument("--resolution", type=float, default=100.0, help="Pixel size in metres (default: 100)")
    p.add_argument("--crs",        default=CRS,               help=f"Target CRS (default: {CRS})")
    p.add_argument("--output",     default=None,              help="Output .tif path (default: same stem as input)")
    args = p.parse_args()
    prepare(args.shp, args.resolution, args.crs, args.output)
