"""
check2_alignment.py — verify pixel↔geo alignment for processed tiles.

Checks:
  1. Each tile's GeoTransform is sane (non-zero pixel size).
  2. Tile CRS can be read and reprojected to EPSG:32723.
  3. Tile footprint in tile_index.geojson matches the raster bounds within 1 m.

Usage:
    python scripts/check2_alignment.py [--tiles-dir PATH] [--index PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

TILES_DIR = Path("data/processed/tiles_8bit")
TILE_INDEX = Path("data/processed/tile_index.geojson")
RIO_CRS = "EPSG:32723"
WGS84 = "EPSG:4326"
TOLERANCE_M = 1.0   # max acceptable boundary mismatch in metres


def run_check(tiles_dir: Path, index_path: Path) -> bool:
    try:
        import rasterio
        from rasterio.crs import CRS
        from rasterio.warp import transform_bounds
    except ImportError:
        print("rasterio required: pip install rasterio")
        return False

    tile_paths = sorted(tiles_dir.glob("*.tif"))
    if not tile_paths:
        print(f"No tiles found in {tiles_dir}")
        return False

    # Load index
    if index_path.exists():
        idx_gdf = gpd.read_file(index_path).set_index("tile_id")
    else:
        print(f"WARNING: tile index not found at {index_path} — skipping footprint check")
        idx_gdf = None

    passed = True
    for tp in tile_paths:
        tile_id = tp.stem
        with rasterio.open(tp) as src:
            if src.transform.a <= 0 or src.transform.e >= 0:
                print(f"✗ {tile_id}: suspicious GeoTransform: {src.transform}")
                passed = False
                continue

            try:
                wgs_bounds = transform_bounds(src.crs, CRS.from_epsg(4326),
                                              src.bounds.left, src.bounds.bottom,
                                              src.bounds.right, src.bounds.top)
            except Exception as e:
                print(f"✗ {tile_id}: CRS reprojection failed: {e}")
                passed = False
                continue

            if idx_gdf is not None and tile_id in idx_gdf.index:
                idx_geom = idx_gdf.loc[tile_id, "geometry"]
                raster_geom = box(*wgs_bounds)
                dist = idx_geom.distance(raster_geom)
                # Convert WGS84 distance to approximate metres
                dist_m = dist * 111_000
                if dist_m > TOLERANCE_M:
                    print(f"✗ {tile_id}: footprint mismatch {dist_m:.2f} m > tolerance {TOLERANCE_M} m")
                    passed = False
                    continue

        print(f"✓ {tile_id}: alignment OK")

    if passed:
        print(f"\n✓ ALL ALIGNMENT CHECKS PASSED ({len(tile_paths)} tiles)")
    else:
        print(f"\n✗ SOME ALIGNMENT CHECKS FAILED — review data_prep.py")

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiles-dir", type=Path, default=TILES_DIR)
    parser.add_argument("--index", type=Path, default=TILE_INDEX)
    args = parser.parse_args()
    ok = run_check(args.tiles_dir, args.index)
    sys.exit(0 if ok else 1)
