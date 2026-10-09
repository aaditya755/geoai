"""
scripts/download_datasets.py — download SkyCLIP checkpoint + SpaceNet v1 Rio data.

Downloads only what is needed for the P1–P3 vertical slice:
  1. SkyCLIP ViT-B/32 checkpoint (1.5 GB) → data/embeddings/
  2. SpaceNet AOI_1_Rio 3-band training tiles (2.57 GB) → data/raw/spacenet_rio/
  3. SpaceNet AOI_1_Rio building GeoJSON labels (21 MB) → data/raw/spacenet_rio/

Does NOT download:
  - SkyScript image dataset (5.2 M pairs, ~180 GB total) — not needed
  - SpaceNet 8-band tiles — SkyCLIP uses RGB only
  - SpaceNet test tiles — not needed until eval (P7)

All data lands in data/ which is git-ignored.

Usage:
    python scripts/download_datasets.py [--skip-checkpoint] [--skip-spacenet] [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# File manifest
# ---------------------------------------------------------------------------

SKYCLIP_CHECKPOINT = {
    "name": "SkyCLIP_ViT_B32_top50pct.zip",
    "url": "https://opendatasharing.s3.us-west-2.amazonaws.com/SkyScript/ckpt/SkyCLIP_ViT_B32_top50pct.zip",
    "dest_dir": "data/embeddings",
    "size_mb": 1515,
    "description": "SkyCLIP ViT-B/32 pretrained checkpoint (SkyScript top-50%)",
}

SPACENET_FILES = [
    {
        "name": "SN1_buildings_train_AOI_1_Rio_3band.tar.gz",
        "url": "https://spacenet-dataset.s3.amazonaws.com/spacenet/SN1_buildings/tarballs/SN1_buildings_train_AOI_1_Rio_3band.tar.gz",
        "dest_dir": "data/raw/spacenet_rio",
        "size_mb": 2572,
        "description": "SpaceNet v1 Rio — 3-band RGB training tiles (200x200m)",
    },
    {
        "name": "SN1_buildings_train_AOI_1_Rio_geojson_buildings.tar.gz",
        "url": "https://spacenet-dataset.s3.amazonaws.com/spacenet/SN1_buildings/tarballs/SN1_buildings_train_AOI_1_Rio_geojson_buildings.tar.gz",
        "dest_dir": "data/raw/spacenet_rio",
        "size_mb": 21,
        "description": "SpaceNet v1 Rio — building footprint GeoJSON labels",
    },
]

ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

class ProgressReporter:
    def __init__(self, total_bytes: int, name: str):
        self.total = total_bytes
        self.name = name
        self.start = time.time()
        self.last_print = 0.0

    def __call__(self, block_count: int, block_size: int, total_size: int):
        downloaded = block_count * block_size
        if total_size > 0:
            pct = min(100.0, downloaded / total_size * 100)
        else:
            pct = 0.0
        elapsed = time.time() - self.start
        mb = downloaded / 1e6
        rate = mb / elapsed if elapsed > 0 else 0
        now = time.time()
        if now - self.last_print >= 5.0 or pct >= 100.0:
            print(f"  {self.name}: {pct:.1f}%  {mb:.0f} MB  {rate:.1f} MB/s", flush=True)
            self.last_print = now


def download_file(url: str, dest_path: Path, size_mb: int, dry_run: bool = False) -> bool:
    """
    Download url to dest_path with progress reporting.
    Skips if dest_path already exists and has a non-zero size.
    Returns True on success, False on failure.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    if dest_path.exists() and dest_path.stat().st_size > 0:
        actual_mb = dest_path.stat().st_size / 1e6
        print(f"  SKIP (already exists, {actual_mb:.0f} MB): {dest_path.name}")
        return True

    if dry_run:
        print(f"  DRY RUN — would download {size_mb} MB → {dest_path}")
        return True

    print(f"  Downloading {dest_path.name} (~{size_mb} MB) …")
    try:
        reporter = ProgressReporter(size_mb * 1_000_000, dest_path.name)
        urllib.request.urlretrieve(url, dest_path, reporthook=reporter)
        actual_mb = dest_path.stat().st_size / 1e6
        print(f"  ✓ {dest_path.name}  ({actual_mb:.0f} MB)")
        return True
    except Exception as e:
        print(f"  ✗ FAILED: {dest_path.name}: {e}")
        if dest_path.exists():
            dest_path.unlink()  # remove partial download
        return False


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def extract_zip(zip_path: Path, dest_dir: Path, dry_run: bool = False) -> list[Path]:
    """Extract a zip and return list of extracted paths."""
    if dry_run:
        print(f"  DRY RUN — would unzip {zip_path.name} → {dest_dir}")
        return []
    print(f"  Extracting {zip_path.name} → {dest_dir} …")
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest_dir)
        extracted = [dest_dir / n for n in zf.namelist()]
    print(f"  ✓ Extracted {len(extracted)} files")
    return extracted


def extract_tar(tar_path: Path, dest_dir: Path, dry_run: bool = False) -> int:
    """Extract a .tar.gz and return count of extracted members."""
    if dry_run:
        print(f"  DRY RUN — would extract {tar_path.name} → {dest_dir}")
        return 0
    print(f"  Extracting {tar_path.name} → {dest_dir} …")
    dest_dir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        members = tf.getmembers()
        tf.extractall(dest_dir)
    print(f"  ✓ Extracted {len(members)} entries")
    return len(members)


# ---------------------------------------------------------------------------
# Post-download inspection
# ---------------------------------------------------------------------------

def inspect_checkpoint(dest_dir: Path) -> None:
    """Report what was extracted from the SkyCLIP checkpoint zip."""
    pt_files = list(dest_dir.rglob("*.pt")) + list(dest_dir.rglob("*.bin"))
    print("\n  SkyCLIP checkpoint contents:")
    for f in pt_files:
        print(f"    {f.relative_to(ROOT)}  ({f.stat().st_size / 1e6:.0f} MB)")
    if not pt_files:
        print("  WARNING: no .pt files found — check zip contents")


def inspect_spacenet(dest_dir: Path) -> None:
    """Report SpaceNet tile count, CRS, and sample bounds."""
    try:
        import rasterio
    except ImportError:
        print("  rasterio not installed — skipping tile inspection")
        return

    tif_files = sorted((dest_dir / "3band").glob("*.tif")) if (dest_dir / "3band").exists() else sorted(dest_dir.rglob("*.tif"))
    if not tif_files:
        print(f"  WARNING: no .tif files found under {dest_dir}")
        return

    print(f"\n  SpaceNet tiles found: {len(tif_files)}")
    # Inspect first tile
    with rasterio.open(tif_files[0]) as src:
        print(f"  Sample tile: {tif_files[0].name}")
        print(f"    CRS: {src.crs}")
        print(f"    Size: {src.width} x {src.height} px")
        print(f"    Bands: {src.count}")
        print(f"    Bounds (native): {src.bounds}")
        print(f"    Dtype: {src.dtypes[0]}")
        from rasterio.warp import transform_bounds
        from rasterio.crs import CRS
        try:
            wgs = transform_bounds(src.crs, CRS.from_epsg(4326),
                                   src.bounds.left, src.bounds.bottom,
                                   src.bounds.right, src.bounds.top)
            print(f"    Bounds (WGS84): {[round(x,4) for x in wgs]}")
        except Exception as e:
            print(f"    WGS84 transform failed: {e}")

    geojson_files = sorted(dest_dir.rglob("*.geojson"))
    print(f"  GeoJSON label files: {len(geojson_files)}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(skip_checkpoint: bool, skip_spacenet: bool, dry_run: bool) -> None:
    import shutil
    total_gb, used_gb, free_gb = (x / 1e9 for x in shutil.disk_usage(str(ROOT)))
    print(f"\nDisk: {free_gb:.1f} GB free of {total_gb:.1f} GB total")

    if free_gb < 6 and not dry_run:
        print("ERROR: less than 6 GB free — aborting to protect disk space.")
        sys.exit(1)

    errors = []

    # --- SkyCLIP checkpoint ---
    if not skip_checkpoint:
        print(f"\n{'='*60}")
        print(f"Checkpoint: {SKYCLIP_CHECKPOINT['description']}")
        print(f"{'='*60}")
        dest_dir = ROOT / SKYCLIP_CHECKPOINT["dest_dir"]
        zip_path = dest_dir / SKYCLIP_CHECKPOINT["name"]

        ok = download_file(
            SKYCLIP_CHECKPOINT["url"], zip_path,
            SKYCLIP_CHECKPOINT["size_mb"], dry_run
        )
        if not ok:
            errors.append(SKYCLIP_CHECKPOINT["name"])
        elif not dry_run and zip_path.exists():
            extract_zip(zip_path, dest_dir, dry_run)
            inspect_checkpoint(dest_dir)

    # --- SpaceNet files ---
    if not skip_spacenet:
        for item in SPACENET_FILES:
            print(f"\n{'='*60}")
            print(f"SpaceNet: {item['description']}")
            print(f"{'='*60}")
            dest_dir = ROOT / item["dest_dir"]
            tar_path = dest_dir / item["name"]

            ok = download_file(item["url"], tar_path, item["size_mb"], dry_run)
            if not ok:
                errors.append(item["name"])
            elif not dry_run and tar_path.exists():
                # Only extract if destination content doesn't already exist
                rgb_dir = dest_dir / "RGB-PanSharpen"
                geojson_dir = dest_dir / "geojson"
                if "3band" in item["name"] and rgb_dir.exists() and any(rgb_dir.glob("*.tif")):
                    print(f"  SKIP extract (RGB-PanSharpen/ already populated)")
                elif "geojson" in item["name"] and geojson_dir.exists() and any(geojson_dir.glob("*.geojson")):
                    print(f"  SKIP extract (geojson/ already populated)")
                else:
                    extract_tar(tar_path, dest_dir, dry_run)

        if not skip_spacenet and not dry_run:
            inspect_spacenet(ROOT / "data/raw/spacenet_rio")

    # --- Summary ---
    print(f"\n{'='*60}")
    if errors:
        print(f"✗ {len(errors)} download(s) failed: {errors}")
        sys.exit(1)
    else:
        print("✓ All downloads complete.")
        if not dry_run:
            print("\nNext steps:")
            print("  1. python data_prep.py --subset 20  (dev run)")
            print("  2. python scripts/check2_alignment.py")
            print("  3. python scripts/check3_tile_meta.py")
            print("  4. Extract pool + road crops from processed tiles")
            print("  5. python scripts/check1_skyclip.py --pool-crop ... --road-crop ...")
            print("  STOP at P3 gate and wait for review.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download GeoLens AI datasets.")
    parser.add_argument("--skip-checkpoint", action="store_true", help="Skip SkyCLIP checkpoint")
    parser.add_argument("--skip-spacenet", action="store_true", help="Skip SpaceNet download")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be downloaded without downloading")
    args = parser.parse_args()
    main(args.skip_checkpoint, args.skip_spacenet, args.dry_run)
