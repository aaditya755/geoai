"""
scripts/post_download_setup.py — automated setup after downloads complete.

Runs the full P1–P3 preparation sequence on downloaded data:
  1. Verify downloads exist and are complete
  2. Extract zip/tarballs if not already extracted
  3. Verify SkyCLIP loads correctly (architecture + embed_dim)
  4. Run data_prep subset (20 tiles)
  5. Run check2_alignment.py
  6. Run check3_tile_meta.py
  7. Extract check1 crops
  8. Run check1_skyclip.py (P3 gate)
  9. Print gate report and STOP for review

Run after `python scripts/download_datasets.py` has completed:
    python scripts/post_download_setup.py [--n-tiles 20] [--skip-check1]

--skip-check1 : run all steps except the final SkyCLIP similarity check
                (useful if you want to inspect alignment first)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import zipfile
import tarfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
EMBEDDINGS_DIR = ROOT / "data/embeddings"
SPACENET_DIR   = ROOT / "data/raw/spacenet_rio"
CROPS_DIR      = ROOT / "data/crops"


# ---------------------------------------------------------------------------
# Step 1: Verify downloads
# ---------------------------------------------------------------------------

def verify_downloads() -> dict:
    """Check all expected download files exist and have expected sizes."""
    results = {}

    files = {
        "skyclip_zip": (EMBEDDINGS_DIR / "SkyCLIP_ViT_B32_top50pct.zip", 1_400_000_000),
        "spacenet_3band": (SPACENET_DIR / "SN1_buildings_train_AOI_1_Rio_3band.tar.gz", 2_400_000_000),
        "spacenet_geojson": (SPACENET_DIR / "SN1_buildings_train_AOI_1_Rio_geojson_buildings.tar.gz", 15_000_000),
    }

    print("\n=== Step 1: Verify downloads ===")
    all_ok = True
    for name, (path, min_bytes) in files.items():
        if path.exists() and path.stat().st_size >= min_bytes:
            print(f"  ✓ {path.name}  ({path.stat().st_size / 1e6:.0f} MB)")
            results[name] = path
        else:
            size_str = f"{path.stat().st_size / 1e6:.0f} MB" if path.exists() else "missing"
            print(f"  ✗ {path.name}  ({size_str})")
            all_ok = False

    if not all_ok:
        print("\nSome downloads are missing or incomplete.")
        print("Run: python scripts/download_datasets.py")
        sys.exit(1)

    return results


# ---------------------------------------------------------------------------
# Step 2: Extract archives
# ---------------------------------------------------------------------------

def extract_archives(files: dict) -> dict:
    """Extract zip and tarballs if not already done."""
    print("\n=== Step 2: Extract archives ===")
    paths = {}

    # SkyCLIP zip
    zip_path = files["skyclip_zip"]
    pt_files = list(EMBEDDINGS_DIR.rglob("*.pt"))
    if pt_files:
        print(f"  SKIP SkyCLIP zip (already extracted: {pt_files[0].name})")
        paths["skyclip_pt"] = pt_files[0]
    else:
        print(f"  Extracting {zip_path.name} …")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(EMBEDDINGS_DIR)
        pt_files = list(EMBEDDINGS_DIR.rglob("*.pt"))
        if not pt_files:
            print("  ✗ No .pt file found after extraction — check zip contents")
            # List what was extracted
            for f in EMBEDDINGS_DIR.rglob("*"):
                if f.is_file():
                    print(f"    {f.relative_to(ROOT)}")
            sys.exit(1)
        paths["skyclip_pt"] = pt_files[0]
        print(f"  ✓ Extracted: {pt_files[0].relative_to(ROOT)}")

    # SpaceNet 3-band
    rgb_dir = SPACENET_DIR / "3band"             # actual extracted directory name
    if rgb_dir.exists() and any(rgb_dir.glob("*.tif")):
        n = len(list(rgb_dir.glob("*.tif")))
        print(f"  SKIP SpaceNet 3band (already extracted: {n} tiles)")
    else:
        tar_path = files["spacenet_3band"]
        print(f"  Extracting {tar_path.name} (~2.57 GB, may take a few minutes) …")
        with tarfile.open(tar_path, "r:gz") as tf:
            tf.extractall(SPACENET_DIR)
        n = len(list(rgb_dir.glob("*.tif"))) if rgb_dir.exists() else 0
        print(f"  ✓ Extracted {n} tiles to {rgb_dir.relative_to(ROOT)}")

    # SpaceNet GeoJSON
    geojson_dir = SPACENET_DIR / "geojson"
    if geojson_dir.exists() and any(geojson_dir.rglob("*.geojson")):
        n = len(list(geojson_dir.rglob("*.geojson")))
        print(f"  SKIP SpaceNet GeoJSON (already extracted: {n} files)")
    else:
        tar_path = files["spacenet_geojson"]
        print(f"  Extracting {tar_path.name} …")
        with tarfile.open(tar_path, "r:gz") as tf:
            tf.extractall(SPACENET_DIR)
        # Geojson files may land at various paths
        n = len(list(SPACENET_DIR.rglob("*.geojson")))
        print(f"  ✓ Extracted {n} GeoJSON files")

    # Report SpaceNet structure
    print(f"\n  SpaceNet directory structure:")
    for p in sorted(SPACENET_DIR.iterdir()):
        if p.is_dir():
            count = len(list(p.rglob("*")))
            print(f"    {p.name}/  ({count} files)")

    return paths


# ---------------------------------------------------------------------------
# Step 3: Verify SkyCLIP loads
# ---------------------------------------------------------------------------

def verify_skyclip(pt_path: Path) -> None:
    """Load SkyCLIP and verify architecture and embed_dim."""
    print("\n=== Step 3: Verify SkyCLIP model ===")

    import os
    os.environ["SKYCLIP_WEIGHTS"] = str(pt_path)

    sys.path.insert(0, str(ROOT))
    from skyclip_loader import load_skyclip, get_embed_dim, get_device

    model, preprocess, tokenizer = load_skyclip()
    arch = getattr(model, "_geolens_arch", "unknown")
    embed_dim = get_embed_dim(model)
    device = get_device()

    print(f"  Architecture: {arch}")
    print(f"  Embed dim:    {embed_dim}")
    print(f"  Device:       {device}")

    # Quick smoke test: embed one text
    import numpy as np
    from skyclip_loader import embed_text
    vec = embed_text(model, tokenizer, "aerial view of a building", device=device)
    assert vec.shape == (embed_dim,), f"Expected shape ({embed_dim},), got {vec.shape}"
    assert abs(np.linalg.norm(vec) - 1.0) < 1e-4, "Feature vector not normalised"
    print(f"  ✓ Text embed smoke test passed: shape={vec.shape}, norm≈{np.linalg.norm(vec):.4f}")

    return arch, embed_dim, device


# ---------------------------------------------------------------------------
# Step 4: Run data_prep subset
# ---------------------------------------------------------------------------

def run_data_prep(n_tiles: int) -> None:
    print(f"\n=== Step 4: data_prep subset ({n_tiles} tiles) ===")
    result = subprocess.run(
        [sys.executable, "scripts/run_data_prep_subset.py", "--n-tiles", str(n_tiles)],
        cwd=str(ROOT), capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        print(f"✗ data_prep failed (exit {result.returncode})")
        sys.exit(1)
    print("  ✓ data_prep subset complete")


# ---------------------------------------------------------------------------
# Steps 5–6: Alignment and metadata checks
# ---------------------------------------------------------------------------

def run_check(script: str, label: str) -> bool:
    print(f"\n=== {label} ===")
    result = subprocess.run(
        [sys.executable, f"scripts/{script}"],
        cwd=str(ROOT), capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode == 0:
        print(f"  ✓ {label} passed")
        return True
    else:
        print(f"  ✗ {label} failed (exit {result.returncode})")
        return False


# ---------------------------------------------------------------------------
# Step 7: Extract crops
# ---------------------------------------------------------------------------

def extract_crops() -> tuple:
    print("\n=== Step 7: Extract check1 crops ===")
    result = subprocess.run(
        [sys.executable, "scripts/extract_check_crops.py"],
        cwd=str(ROOT), capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
        sys.exit(1)

    pool_crop = CROPS_DIR / "check1_pool_proxy.png"
    road_crop = CROPS_DIR / "check1_road_proxy.png"

    if not pool_crop.exists() or not road_crop.exists():
        print("✗ Crop files not found after extraction")
        sys.exit(1)

    print(f"  pool_crop: {pool_crop.relative_to(ROOT)}")
    print(f"  road_crop: {road_crop.relative_to(ROOT)}")
    return pool_crop, road_crop


# ---------------------------------------------------------------------------
# Step 8: Run check1 (P3 gate)
# ---------------------------------------------------------------------------

def run_check1(pool_crop: Path, road_crop: Path) -> None:
    print("\n=== Step 8: check1_skyclip.py (P3 GATE) ===")
    result = subprocess.run(
        [sys.executable, "scripts/check1_skyclip.py",
         "--pool-crop", str(pool_crop),
         "--road-crop", str(road_crop)],
        cwd=str(ROOT), capture_output=True, text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    passed = result.returncode == 0
    print(f"\n{'✓ P3 GATE PASSED' if passed else '✗ P3 GATE FAILED'}")
    print("\n" + "="*60)
    print("STOP — review the results above before proceeding to P4.")
    print("Fill in docs/phase_gate_report_template.md with these values.")
    print("="*60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(n_tiles: int, skip_check1: bool) -> None:
    files = verify_downloads()
    paths = extract_archives(files)

    pt_path = paths["skyclip_pt"]
    verify_skyclip(pt_path)

    run_data_prep(n_tiles)
    align_ok = run_check("check2_alignment.py", "Step 5: check2_alignment.py")
    meta_ok  = run_check("check3_tile_meta.py",  "Step 6: check3_tile_meta.py")

    if not align_ok or not meta_ok:
        print("\n✗ Alignment or metadata check failed — fix before check1.")
        sys.exit(1)

    pool_crop, road_crop = extract_crops()

    if skip_check1:
        print("\nSkipping check1 (--skip-check1 set).")
        print(f"Run manually:\n  python scripts/check1_skyclip.py "
              f"--pool-crop {pool_crop} --road-crop {road_crop}")
    else:
        run_check1(pool_crop, road_crop)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-tiles", type=int, default=20)
    parser.add_argument("--skip-check1", action="store_true")
    args = parser.parse_args()
    main(args.n_tiles, args.skip_check1)
