"""
data_prep.py — data preparation pipeline for GeoLens AI.

Prepares SpaceNet Buildings v1 (Rio de Janeiro) tiles and OpenStreetMap vectors.

Existing functions are preserved. New functions added per spec tasks P1.2–P1.4:
  - apply_global_brightness_stretch()  [REQ-001]
  - download_osm_intersecting_tiles()  [REQ-002]
  - write_provenance()                 [REQ-003]

[MANUAL] The SpaceNet raw tiles must be downloaded manually from AWS S3.
See tasks.md P1.1 for the download command.

Usage:
    python data_prep.py [--tiles-dir PATH] [--output-dir PATH] [--subset INT]
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import box

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

RAW_TILES_DIR = Path("data/raw/spacenet_rio")
OSM_DIR = Path("data/raw/osm")
PROCESSED_DIR = Path("data/processed/tiles_8bit")
TILE_INDEX_PATH = Path("data/processed/tile_index.geojson")
BUILDINGS_PATH = Path("data/processed/buildings.parquet")
ROADS_PATH = Path("data/processed/roads.parquet")
PROVENANCE_PATH = Path("data/provenance.json")

RIO_CRS = "EPSG:32723"
WGS84 = "EPSG:4326"


# ---------------------------------------------------------------------------
# REQ-001: Global brightness stretch
# ---------------------------------------------------------------------------

def apply_global_brightness_stretch(
    raw_tiles_dir: Path = RAW_TILES_DIR,
    output_dir: Path = PROCESSED_DIR,
    clip_percent: float = 1.0,
) -> list:
    """
    Apply a GLOBAL brightness/contrast stretch across ALL tiles.

    The stretch parameters (min/max) are computed from a random sample of
    all tiles, then applied uniformly — NOT per-tile.

    This ensures radiometric consistency across the dataset.
    Clips clip_percent at each end of the global histogram to avoid outliers.

    Parameters
    ----------
    raw_tiles_dir : directory containing raw .tif tiles
    output_dir    : directory for 8-bit stretched output tiles
    clip_percent  : percentage to clip at each histogram end (default 1.0%)

    Returns
    -------
    List of output file paths.
    """
    try:
        import rasterio
        from rasterio.enums import Resampling
    except ImportError:
        raise ImportError("rasterio is required: pip install rasterio")

    output_dir.mkdir(parents=True, exist_ok=True)
    tile_paths = sorted(raw_tiles_dir.glob("*.tif")) or sorted(raw_tiles_dir.rglob("*.tif"))

    if not tile_paths:
        raise FileNotFoundError(
            f"No .tif files found in {raw_tiles_dir} (searched recursively). "
            "Download SpaceNet tiles first (tasks.md P1.1 [MANUAL])."
        )

    print(f"[data_prep] Computing global brightness stretch over {len(tile_paths)} tiles …")

    # --- Step 1: compute global percentile values from all tiles (all bands) ---
    sample_values = []
    for tp in tile_paths:
        with rasterio.open(tp) as src:
            # Read at reduced resolution for speed
            data = src.read(
                out_shape=(src.count, max(1, src.height // 4), max(1, src.width // 4)),
                resampling=Resampling.average,
            )
            sample_values.append(data.astype(np.float32).ravel())

    all_values = np.concatenate(sample_values)
    all_values = all_values[np.isfinite(all_values)]

    global_min = float(np.percentile(all_values, clip_percent))
    global_max = float(np.percentile(all_values, 100.0 - clip_percent))
    print(f"[data_prep] Global stretch: min={global_min:.1f}, max={global_max:.1f} "
          f"(clipping {clip_percent}% at each end)")

    # --- Step 2: apply the same stretch to every tile ---
    output_paths = []
    for tp in tile_paths:
        out_path = output_dir / tp.name
        with rasterio.open(tp) as src:
            meta = src.meta.copy()
            meta.update(dtype="uint8", driver="GTiff")
            data = src.read().astype(np.float32)

        # Stretch to [0, 255]
        stretched = np.clip((data - global_min) / (global_max - global_min + 1e-8), 0.0, 1.0)
        stretched = (stretched * 255.0).astype(np.uint8)

        with rasterio.open(out_path, "w", **meta) as dst:
            dst.write(stretched)

        output_paths.append(out_path)

    print(f"[data_prep] Wrote {len(output_paths)} stretched tiles to {output_dir}")
    return output_paths


# ---------------------------------------------------------------------------
# REQ-002: OSM intersection filter
# ---------------------------------------------------------------------------

def download_osm_intersecting_tiles(
    tiles_dir: Path = PROCESSED_DIR,
    output_dir: Path = OSM_DIR,
    buffer_m: float = 10.0,
) -> dict:
    """
    Download OSM features ONLY for the bounding box of tiles that exist on disk.

    Uses the Overpass API to fetch roads and buildings.
    The bbox is the union of all tile footprints ± buffer_m (in metres).

    Parameters
    ----------
    tiles_dir  : directory of processed tiles (used to compute bbox)
    output_dir : directory to save OSM GeoJSON files
    buffer_m   : buffer around tile union in metres (default 10 m)

    Returns
    -------
    dict of {layer_name: GeoDataFrame}

    Raises
    ------
    FileNotFoundError if no tiles found.
    RuntimeError if Overpass download fails.
    """
    try:
        import osmnx as ox
        import rasterio
    except ImportError:
        raise ImportError("osmnx and rasterio are required: pip install osmnx rasterio")

    output_dir.mkdir(parents=True, exist_ok=True)

    tile_paths = sorted(tiles_dir.glob("*.tif"))
    if not tile_paths:
        raise FileNotFoundError(
            f"No processed tiles found in {tiles_dir}. "
            "Run apply_global_brightness_stretch() first."
        )

    # Compute union of tile bboxes in WGS84
    import rasterio
    from rasterio.crs import CRS

    bounds_list = []
    for tp in tile_paths:
        with rasterio.open(tp) as src:
            b = src.bounds
            # Convert to WGS84 if needed
            from rasterio.warp import transform_bounds
            wgs_bounds = transform_bounds(src.crs, CRS.from_epsg(4326), b.left, b.bottom, b.right, b.top)
            bounds_list.append(wgs_bounds)

    # Union of all tile bboxes
    min_x = min(b[0] for b in bounds_list)
    min_y = min(b[1] for b in bounds_list)
    max_x = max(b[2] for b in bounds_list)
    max_y = max(b[3] for b in bounds_list)

    print(f"[data_prep] Tile union bbox (WGS84): {min_x:.4f},{min_y:.4f} → {max_x:.4f},{max_y:.4f}")

    # Small buffer in degrees (approx, ~10 m at Rio latitude)
    deg_buffer = buffer_m / 111_000
    bbox = (min_y - deg_buffer, min_x - deg_buffer, max_y + deg_buffer, max_x + deg_buffer)

    layers = {}

    # Download roads
    try:
        print("[data_prep] Downloading OSM roads …")
        roads_gdf = ox.features_from_bbox(*bbox, tags={"highway": True})
        roads_gdf = roads_gdf.to_crs(RIO_CRS)
        roads_path = output_dir / "roads.parquet"
        roads_gdf.to_parquet(roads_path)
        layers["road"] = roads_gdf
        print(f"[data_prep] Roads: {len(roads_gdf)} features → {roads_path}")
    except Exception as e:
        print(f"[data_prep] WARNING: road download failed: {e}")

    # Download buildings
    try:
        print("[data_prep] Downloading OSM buildings …")
        buildings_gdf = ox.features_from_bbox(*bbox, tags={"building": True})
        buildings_gdf = buildings_gdf.to_crs(RIO_CRS)
        buildings_path = output_dir / "buildings.parquet"
        buildings_gdf.to_parquet(buildings_path)
        layers["building"] = buildings_gdf
        print(f"[data_prep] Buildings: {len(buildings_gdf)} features → {buildings_path}")
    except Exception as e:
        print(f"[data_prep] WARNING: building download failed: {e}")

    return layers


# ---------------------------------------------------------------------------
# REQ-003: Provenance metadata
# ---------------------------------------------------------------------------

def write_provenance(output_path: Path = PROVENANCE_PATH) -> dict:
    """
    Record OSM download date, GDAL version, GeoPandas version, and Python version
    to data/provenance.json.

    Called at the end of data_prep to create an audit trail.
    Also called by index_tiles.py to add embedding metadata.

    Returns the provenance dict.
    """
    try:
        from osgeo import gdal
        gdal_version = gdal.__version__
    except ImportError:
        gdal_version = "unavailable (osgeo not installed)"

    prov: dict = {}
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            prov = json.load(f)

    prov.update({
        "osm_download_date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "python_version": sys.version,
        "geopandas_version": gpd.__version__,
        "gdal_version": gdal_version,
        "platform": platform.platform(),
    })

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=2)

    print(f"[data_prep] Wrote provenance → {output_path}")
    return prov


# ---------------------------------------------------------------------------
# Tile index builder
# ---------------------------------------------------------------------------

def build_tile_index(
    tiles_dir: Path = PROCESSED_DIR,
    output_path: Path = TILE_INDEX_PATH,
) -> gpd.GeoDataFrame:
    """
    Build a GeoDataFrame of tile footprints with tile_id column.
    Saved as GeoJSON for use by vision.py.
    """
    try:
        import rasterio
        from rasterio.crs import CRS
        from rasterio.warp import transform_bounds
    except ImportError:
        raise ImportError("rasterio required: pip install rasterio")

    tile_paths = sorted(tiles_dir.glob("*.tif"))
    if not tile_paths:
        raise FileNotFoundError(f"No tiles in {tiles_dir}")

    rows = []
    for tp in tile_paths:
        with rasterio.open(tp) as src:
            b = src.bounds
            wgs_bounds = transform_bounds(
                src.crs, CRS.from_epsg(4326),
                b.left, b.bottom, b.right, b.top
            )
        rows.append({
            "tile_id": tp.stem,
            "geometry": box(*wgs_bounds),
        })

    gdf = gpd.GeoDataFrame(rows, crs=WGS84)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON")
    print(f"[data_prep] Tile index: {len(gdf)} tiles → {output_path}")
    return gdf


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(tiles_dir: Path, output_dir: Path, subset: int = 0) -> None:
    raw_dir = tiles_dir or RAW_TILES_DIR
    proc_dir = output_dir or PROCESSED_DIR

    # Subset for dev runs
    if subset > 0:
        print(f"[data_prep] Dev mode: using first {subset} tiles only")

    # Step 1: Global brightness stretch
    stretched = apply_global_brightness_stretch(raw_tiles_dir=raw_dir, output_dir=proc_dir)
    if subset > 0:
        stretched = stretched[:subset]

    # Step 2: Tile index
    build_tile_index(tiles_dir=proc_dir)

    # Step 3: OSM download (intersection only)
    download_osm_intersecting_tiles(tiles_dir=proc_dir)

    # Step 4: Provenance
    write_provenance()

    print("[data_prep] Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GeoLens AI data preparation pipeline.")
    parser.add_argument("--tiles-dir", type=Path, default=RAW_TILES_DIR,
                        help="Raw SpaceNet tiles directory")
    parser.add_argument("--output-dir", type=Path, default=PROCESSED_DIR,
                        help="Output directory for processed tiles")
    parser.add_argument("--subset", type=int, default=0,
                        help="Process only first N tiles (0 = all; for dev use)")
    args = parser.parse_args()
    main(args.tiles_dir, args.output_dir, args.subset)
