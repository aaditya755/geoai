"""
scripts/dataset_preflight.py — dataset inspection report for GeoLens AI.

Inspects whatever files actually exist on disk and reports honestly.
Does NOT invent file paths, feature counts, or coverage numbers.
Run this before P1 to understand what data is available.

Usage:
    python scripts/dataset_preflight.py [--tiles-dir PATH] [--osm-dir PATH] [--output PATH]

Output: a markdown report saved to docs/dataset_preflight_report.md
(or --output path), plus printed to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
import datetime
from pathlib import Path

# Defaults
TILES_DIR = Path("data/raw/spacenet_rio")
OSM_DIR = Path("data/raw/osm")
OUTPUT_PATH = Path("docs/dataset_preflight_report.md")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hr() -> str:
    return "\n---\n"


def _section(title: str) -> str:
    return f"\n## {title}\n"


# ---------------------------------------------------------------------------
# Tile inspection
# ---------------------------------------------------------------------------

def inspect_tiles(tiles_dir: Path) -> str:
    lines = [_section("1. SpaceNet Imagery Tiles")]

    if not tiles_dir.exists():
        lines.append(
            f"**Directory not found:** `{tiles_dir}`\n\n"
            "The SpaceNet Buildings v1 tiles have not been downloaded yet.\n"
            "Run the manual download step (tasks.md P1.1) before proceeding with P1.\n\n"
            "```\n"
            "aws s3 cp s3://spacenet-dataset/spacenet/SN1_buildings/  "
            "data/raw/spacenet_rio/  --recursive\n"
            "```\n"
        )
        return "".join(lines)

    tile_paths = sorted(tiles_dir.rglob("*.tif"))
    png_paths = sorted(tiles_dir.rglob("*.png"))
    all_raster = tile_paths + png_paths

    lines.append(f"**Directory:** `{tiles_dir.resolve()}`\n")
    lines.append(f"**Files found:** {len(all_raster)} raster files "
                 f"({len(tile_paths)} .tif, {len(png_paths)} .png)\n")

    if not all_raster:
        lines.append("\nNo raster files found. Directory exists but is empty.\n")
        return "".join(lines)

    try:
        import rasterio
        from rasterio.crs import CRS
        from rasterio.warp import transform_bounds

        sample_info = []
        crs_set = set()
        dims_list = []
        bounds_list = []
        band_counts = set()
        dtypes = set()

        for tp in all_raster[:20]:   # inspect up to 20 tiles
            try:
                with rasterio.open(tp) as src:
                    crs_set.add(src.crs.to_string() if src.crs else "None")
                    dims_list.append((src.width, src.height))
                    band_counts.add(src.count)
                    dtypes.add(str(src.dtypes[0]))
                    try:
                        wb = transform_bounds(
                            src.crs, CRS.from_epsg(4326),
                            src.bounds.left, src.bounds.bottom,
                            src.bounds.right, src.bounds.top,
                        )
                        bounds_list.append(wb)
                    except Exception:
                        pass

                    if len(sample_info) < 3:
                        sample_info.append({
                            "file": tp.name,
                            "size": f"{src.width}×{src.height}",
                            "bands": src.count,
                            "dtype": src.dtypes[0],
                            "crs": str(src.crs) if src.crs else "None",
                            "transform": str(src.transform),
                        })
            except Exception as e:
                sample_info.append({"file": tp.name, "error": str(e)})

        lines.append(f"\n**CRS values observed:** {', '.join(crs_set) or 'none'}\n")
        lines.append(f"**Band counts observed:** {', '.join(str(b) for b in sorted(band_counts))}\n")
        lines.append(f"**Pixel dtypes observed:** {', '.join(sorted(dtypes))}\n")

        if dims_list:
            w_vals = [d[0] for d in dims_list]
            h_vals = [d[1] for d in dims_list]
            lines.append(
                f"**Width range (px):** {min(w_vals)}–{max(w_vals)}\n"
                f"**Height range (px):** {min(h_vals)}–{max(h_vals)}\n"
            )

        if bounds_list:
            min_x = min(b[0] for b in bounds_list)
            min_y = min(b[1] for b in bounds_list)
            max_x = max(b[2] for b in bounds_list)
            max_y = max(b[3] for b in bounds_list)
            lines.append(
                f"**Coverage bbox (WGS84, from sample):** "
                f"{min_x:.4f}, {min_y:.4f} → {max_x:.4f}, {max_y:.4f}\n"
            )

        lines.append("\n**Sample files (up to 3):**\n\n```\n")
        for s in sample_info[:3]:
            lines.append(json.dumps(s, indent=2) + "\n")
        lines.append("```\n")

        # Pixel resolution estimate (unverified)
        if dims_list and bounds_list:
            w = dims_list[0][0]
            b = bounds_list[0]
            deg_per_px = (b[2] - b[0]) / w if w > 0 else 0
            m_per_px = deg_per_px * 111_000
            lines.append(
                f"\n**Estimated ground resolution (first tile, approx):** "
                f"~{m_per_px:.2f} m/px "
                f"(assumes 1° ≈ 111 km; unverified — confirm from SpaceNet metadata)\n"
            )

    except ImportError:
        lines.append(
            "\n`rasterio` not installed — cannot inspect raster metadata. "
            "Install with `pip install rasterio`.\n"
        )

    return "".join(lines)


# ---------------------------------------------------------------------------
# OSM inspection
# ---------------------------------------------------------------------------

def inspect_osm(osm_dir: Path) -> str:
    lines = [_section("2. OpenStreetMap Data")]

    if not osm_dir.exists():
        lines.append(
            f"**Directory not found:** `{osm_dir}`\n\n"
            "OSM data has not been downloaded yet.\n"
            "Run `data_prep.py` after downloading the SpaceNet tiles (P1.3).\n"
        )
        return "".join(lines)

    parquet_files = sorted(osm_dir.glob("*.parquet"))
    geojson_files = sorted(osm_dir.glob("*.geojson"))
    all_osm = parquet_files + geojson_files

    lines.append(f"**Directory:** `{osm_dir.resolve()}`\n")
    lines.append(f"**Files found:** {len(all_osm)} "
                 f"({len(parquet_files)} .parquet, {len(geojson_files)} .geojson)\n")

    if not all_osm:
        lines.append("\nNo OSM files found. Run `data_prep.py` first.\n")
        return "".join(lines)

    try:
        import geopandas as gpd

        for f in all_osm:
            lines.append(f"\n**File:** `{f.name}`\n")
            try:
                if f.suffix == ".parquet":
                    gdf = gpd.read_parquet(f)
                else:
                    gdf = gpd.read_file(f)

                lines.append(f"- Rows: {len(gdf)}\n")
                lines.append(f"- CRS: {gdf.crs}\n")
                lines.append(f"- Geometry types: {gdf.geometry.geom_type.unique().tolist()}\n")

                # Report observed tag columns (only non-geometry, non-index)
                tag_cols = [c for c in gdf.columns if c not in ("geometry", "index")]
                if tag_cols:
                    lines.append(f"- Columns: {tag_cols[:20]}\n")

                # For roads: report observed highway values
                if "highway" in gdf.columns:
                    vals = gdf["highway"].dropna().unique().tolist()[:20]
                    lines.append(f"- highway values observed: {vals}\n")

                # For buildings: report observed building values
                if "building" in gdf.columns:
                    vals = gdf["building"].dropna().unique().tolist()[:20]
                    lines.append(f"- building values observed: {vals}\n")

                # Bbox
                if not gdf.empty:
                    b = gdf.total_bounds
                    lines.append(f"- Bbox: {b[0]:.2f}, {b[1]:.2f} → {b[2]:.2f}, {b[3]:.2f}\n")

            except Exception as e:
                lines.append(f"- Error reading file: {e}\n")

    except ImportError:
        lines.append(
            "\n`geopandas` not installed — cannot inspect OSM files. "
            "Install with `pip install geopandas`.\n"
        )

    return "".join(lines)


# ---------------------------------------------------------------------------
# Tile / OSM coverage overlap
# ---------------------------------------------------------------------------

def inspect_overlap(tiles_dir: Path, osm_dir: Path) -> str:
    lines = [_section("3. Tile / OSM Coverage Overlap")]

    tile_index = Path("data/processed/tile_index.geojson")
    osm_roads = osm_dir / "roads.parquet"

    if not tile_index.exists():
        lines.append(
            f"`data/processed/tile_index.geojson` not found. "
            "Run `data_prep.py` first to build the tile index.\n"
        )
        return "".join(lines)

    if not osm_roads.exists():
        lines.append(
            f"`{osm_roads}` not found. Cannot compute overlap. "
            "Run `data_prep.py` first.\n"
        )
        return "".join(lines)

    try:
        import geopandas as gpd
        from shapely.ops import unary_union

        tiles_gdf = gpd.read_file(tile_index)
        roads_gdf = gpd.read_parquet(osm_roads)

        tiles_union = tiles_gdf.geometry.union_all()
        roads_union = roads_gdf.geometry.union_all()

        overlap = tiles_union.intersection(roads_union)
        overlap_area = overlap.area if not overlap.is_empty else 0.0
        tiles_area = tiles_union.area

        lines.append(f"- Tile footprints: {len(tiles_gdf)}\n")
        lines.append(f"- Road features: {len(roads_gdf)}\n")
        lines.append(
            f"- Overlap (road lines intersecting tile bbox): "
            f"{'yes' if overlap_area > 0 else 'no'}\n"
        )

    except Exception as e:
        lines.append(f"Error computing overlap: {e}\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Missing data and limitations
# ---------------------------------------------------------------------------

def missing_data_section() -> str:
    return _section("4. Missing Data, Limitations and Unsupported Concepts") + """
The following are known at design time (see `design.md §8` for the full
unverified-assumptions list):

| Item | Status | Notes |
|------|--------|-------|
| SpaceNet Buildings v1 tiles | **[MANUAL download required]** | See tasks.md P1.1 |
| SpaceNet tile CRS | Unverified | Must be read from tile header |
| SpaceNet pixel resolution | Unverified (~0.5 m/px assumed) | Confirm from metadata |
| SkyCLIP weights | **[MANUAL download/GPU required]** | See tasks.md P3.2, P3.3 |
| FAISS index | **[MANUAL GPU run required]** | See tasks.md P3.3 |
| OSM coverage completeness | Unverified | Varies by neighbourhood |
| Solar panels | Not reliably detectable at ~0.5 m/px | Returns "too small to see" |
| Narrow drains | Not reliably detectable | Returns OSM fallback only |
| Sarvam AI endpoint | Unverified | See translate.py TODO |
| Jev AI API | Unverified | Stub only; uses local scorer |
| Mistral API | Needs real key | Fallback planner used until key provided |

"""


# ---------------------------------------------------------------------------
# P2 vertical-slice query recommendation
# ---------------------------------------------------------------------------

def p2_query_recommendation(tiles_dir: Path, osm_dir: Path) -> str:
    lines = [_section("5. Recommended P2 OSM-only Vertical Slice Query")]

    roads_path = osm_dir / "roads.parquet"
    parks_path = osm_dir / "parks.parquet"

    if not roads_path.exists():
        lines.append(
            "**Cannot recommend a query yet** — OSM data not downloaded.\n\n"
            "After running `data_prep.py`, re-run this script to get a data-driven recommendation.\n\n"
            "**Default recommendation (subject to data availability):**\n\n"
            "> `\"primary roads within 500 m of the dataset boundary\"`\n\n"
            "Rationale: roads (`highway=*`) are the most reliably mapped OSM feature "
            "in urban Rio de Janeiro. A `dwithin` query exercises plan parsing, "
            "spatial filtering, measured_distance_m output, the API response schema, "
            "and map rendering — the full P2 vertical slice — without requiring "
            "any vision model inference.\n\n"
            "**Confirm this choice after running data_prep.py and verifying that "
            "roads are present in the OSM extract.**\n"
        )
        return "".join(lines)

    try:
        import geopandas as gpd

        roads_gdf = gpd.read_parquet(roads_path)
        n_roads = len(roads_gdf)
        highway_vals = roads_gdf.get("highway", gpd.pd.Series()).dropna().unique().tolist()[:10]

        lines.append(
            f"OSM roads layer found: **{n_roads} features**.\n"
            f"Highway values present: {highway_vals}\n\n"
        )

        if n_roads > 0:
            lines.append(
                "**Recommended P2 query:**\n\n"
                "> `\"primary roads within 500 m of the tile boundary\"`\n\n"
                "This query:\n"
                "- Uses `osm_only` grounding (no vision model required)\n"
                "- Exercises `dwithin` spatial filtering with a real OSM layer\n"
                "- Produces a non-empty result set (roads are present)\n"
                "- Exercises `measured_distance_m` output\n"
                "- Is the smallest deterministic query that covers all P2 acceptance criteria\n\n"
                "**Alternative if primary roads are sparse:** use `highway=*` (all roads).\n"
            )
        else:
            lines.append(
                "Roads layer is empty. Cannot recommend a data-driven query.\n"
                "Review OSM download in `data_prep.py`.\n"
            )

    except Exception as e:
        lines.append(f"Error reading roads layer: {e}\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(tiles_dir: Path, osm_dir: Path, output: Path) -> None:
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    report = f"# GeoLens AI — Dataset Preflight Report\n\n"
    report += f"Generated: {timestamp} UTC  \n"
    report += f"Tiles dir: `{tiles_dir}`  \n"
    report += f"OSM dir: `{osm_dir}`  \n"
    report += "\n> **Note:** This report reflects only what is actually present on disk.\n"
    report += "> No file paths, feature counts, or coverage numbers are invented.\n"
    report += _hr()

    report += inspect_tiles(tiles_dir)
    report += _hr()
    report += inspect_osm(osm_dir)
    report += _hr()
    report += inspect_overlap(tiles_dir, osm_dir)
    report += _hr()
    report += missing_data_section()
    report += _hr()
    report += p2_query_recommendation(tiles_dir, osm_dir)

    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\nReport saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GeoLens AI dataset preflight inspection.")
    parser.add_argument("--tiles-dir", type=Path, default=TILES_DIR)
    parser.add_argument("--osm-dir", type=Path, default=OSM_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()
    main(args.tiles_dir, args.osm_dir, args.output)
