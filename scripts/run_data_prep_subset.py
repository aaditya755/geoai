"""
scripts/run_data_prep_subset.py — run data_prep on a small SpaceNet subset.

SpaceNet v1 Rio 3-band tiles are stored as:
  data/raw/spacenet_rio/RGB-PanSharpen/RGB-PanSharpen_AOI_1_RIO_img<N>.tif

This script:
  1. Finds the RGB-PanSharpen directory
  2. Copies the first N tiles to a temp input directory
  3. Runs data_prep.py's individual functions on that subset
  4. Reports provenance.json, tile count, and sample CRS/bounds

Run after download_datasets.py has completed and extracted the tarballs.

Usage:
    python scripts/run_data_prep_subset.py [--n-tiles 20]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
RGB_DIR = ROOT / "data/raw/spacenet_rio/3band"        # actual extracted path
GEOJSON_DIR = ROOT / "data/raw/spacenet_rio/geojson"
PROCESSED_DIR = ROOT / "data/processed/tiles_8bit"
PROVENANCE_PATH = ROOT / "data/provenance.json"


def find_rgb_tiles(n: int) -> list:
    if not RGB_DIR.exists():
        print(f"ERROR: {RGB_DIR} does not exist.")
        print("Run: python scripts/download_datasets.py")
        sys.exit(1)
    tiles = sorted(RGB_DIR.glob("*.tif"))
    if not tiles:
        print(f"ERROR: no .tif files in {RGB_DIR}")
        sys.exit(1)
    print(f"Found {len(tiles)} tiles in {RGB_DIR}")
    return tiles[:n]


def main(n_tiles: int) -> None:
    import sys
    sys.path.insert(0, str(ROOT))

    tiles = find_rgb_tiles(n_tiles)
    print(f"Using first {len(tiles)} tiles for dev subset\n")

    # Show what we'll be working with
    try:
        import rasterio
        from rasterio.crs import CRS
        from rasterio.warp import transform_bounds

        print("Sample tile metadata:")
        for tp in tiles[:3]:
            with rasterio.open(tp) as src:
                b = src.bounds
                try:
                    wgs = transform_bounds(src.crs, CRS.from_epsg(4326),
                                           b.left, b.bottom, b.right, b.top)
                    wgs_str = f"WGS84: [{wgs[0]:.4f},{wgs[1]:.4f},{wgs[2]:.4f},{wgs[3]:.4f}]"
                except Exception:
                    wgs_str = "WGS84: (could not reproject)"
                print(f"  {tp.name}: {src.width}x{src.height}px, bands={src.count}, "
                      f"CRS={src.crs}, dtype={src.dtypes[0]}, {wgs_str}")
    except ImportError:
        print("rasterio not available — skipping tile inspection")

    # Run data_prep steps
    from data_prep import (
        apply_global_brightness_stretch,
        build_tile_index,
        write_provenance,
    )

    print(f"\nStep 1: Global brightness stretch ({n_tiles} tiles) …")
    # Create a temp tiles dir with symlinks/copies of subset
    import shutil
    tmp_raw = ROOT / "data/raw/spacenet_rio/_subset_tmp"
    tmp_raw.mkdir(parents=True, exist_ok=True)
    for tp in tiles:
        dest = tmp_raw / tp.name
        if not dest.exists():
            shutil.copy2(tp, dest)

    stretched = apply_global_brightness_stretch(
        raw_tiles_dir=tmp_raw,
        output_dir=PROCESSED_DIR,
    )
    print(f"  Stretched {len(stretched)} tiles → {PROCESSED_DIR}")

    print("\nStep 2: Build tile index …")
    gdf = build_tile_index(tiles_dir=PROCESSED_DIR)
    print(f"  Tile index: {len(gdf)} tiles → data/processed/tile_index.geojson")

    print("\nStep 3: Write provenance …")
    prov = write_provenance(PROVENANCE_PATH)
    print(f"  Provenance: {prov}")

    # Clean up temp dir
    shutil.rmtree(tmp_raw, ignore_errors=True)

    print(f"\n✓ data_prep subset complete ({n_tiles} tiles).")
    print("Next: python scripts/check2_alignment.py")
    print("      python scripts/check3_tile_meta.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-tiles", type=int, default=20)
    args = parser.parse_args()
    main(args.n_tiles)
