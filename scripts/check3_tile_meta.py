"""
check3_tile_meta.py — verify tile metadata completeness.

Checks that every tile in the processed directory:
  1. Is present in tile_index.geojson.
  2. Has valid bounds (not degenerate).
  3. provenance.json exists and has required keys.

Usage:
    python scripts/check3_tile_meta.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd

TILES_DIR = Path("data/processed/tiles_8bit")
TILE_INDEX = Path("data/processed/tile_index.geojson")
PROVENANCE = Path("data/provenance.json")

REQUIRED_PROV_KEYS = {"osm_download_date", "python_version", "geopandas_version", "gdal_version"}


def run_check() -> bool:
    passed = True

    # Check provenance.json
    if not PROVENANCE.exists():
        print(f"✗ provenance.json not found at {PROVENANCE}")
        passed = False
    else:
        with open(PROVENANCE) as f:
            prov = json.load(f)
        missing = REQUIRED_PROV_KEYS - set(prov.keys())
        if missing:
            print(f"✗ provenance.json missing keys: {missing}")
            passed = False
        else:
            print(f"✓ provenance.json: all required keys present")

    # Check tile index
    if not TILE_INDEX.exists():
        print(f"✗ tile_index.geojson not found at {TILE_INDEX}")
        passed = False
        return passed

    idx_gdf = gpd.read_file(TILE_INDEX)
    indexed_ids = set(idx_gdf["tile_id"].tolist())
    tile_paths = sorted(TILES_DIR.glob("*.tif"))

    for tp in tile_paths:
        tile_id = tp.stem
        if tile_id not in indexed_ids:
            print(f"✗ {tile_id}: not in tile_index.geojson")
            passed = False
        else:
            geom = idx_gdf[idx_gdf["tile_id"] == tile_id].geometry.iloc[0]
            b = geom.bounds
            if b[2] <= b[0] or b[3] <= b[1]:
                print(f"✗ {tile_id}: degenerate bounds {b}")
                passed = False
            else:
                print(f"✓ {tile_id}: in index, bounds OK")

    if passed:
        print(f"\n✓ ALL METADATA CHECKS PASSED ({len(tile_paths)} tiles)")
    else:
        print(f"\n✗ SOME METADATA CHECKS FAILED")

    return passed


if __name__ == "__main__":
    ok = run_check()
    sys.exit(0 if ok else 1)
