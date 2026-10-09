"""
index_tiles.py — build the SkyCLIP FAISS index from processed tiles.

[MANUAL — GPU] This script is intended to be run on a GPU machine (Colab/Kaggle).
It reads tiles from data/processed/tiles_8bit/, embeds them with SkyCLIP
using multi-crop mean-pooling, and writes the FAISS index to
data/embeddings/skyclip.index plus a metadata JSON.

Usage:
    python index_tiles.py [--tiles-dir PATH] [--output-dir PATH] [--n-crops INT]

Environment variables:
    SKYCLIP_WEIGHTS — path to local SkyCLIP .pt weights file
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

DEFAULT_TILES_DIR = Path("data/processed/tiles_8bit")
DEFAULT_OUTPUT_DIR = Path("data/embeddings")
DEFAULT_N_CROPS = 3
DEFAULT_CROP_SIZE = 224


def build_index(
    tiles_dir: Path,
    output_dir: Path,
    n_crops: int = DEFAULT_N_CROPS,
    crop_size: int = DEFAULT_CROP_SIZE,
) -> None:
    import faiss
    from PIL import Image

    from skyclip_loader import embed_crops, get_device, load_skyclip, make_crops

    output_dir.mkdir(parents=True, exist_ok=True)
    tile_paths = sorted(tiles_dir.glob("*.tif")) + sorted(tiles_dir.glob("*.png"))

    if not tile_paths:
        raise FileNotFoundError(
            f"No .tif or .png tiles found in {tiles_dir}. "
            "Run data_prep.py first (task P1.2)."
        )

    print(f"[index_tiles] Found {len(tile_paths)} tiles in {tiles_dir}")
    print(f"[index_tiles] Loading SkyCLIP model …")
    model, preprocess, tokenizer = load_skyclip()
    device = get_device()
    arch = getattr(model, "_geolens_arch", "unknown")
    print(f"[index_tiles] Device: {device}, Architecture: {arch}")

    embeddings = []
    meta = []   # list of {"tile_id": str, "crop_offsets": [[y,x], ...]}

    t0 = time.time()
    for i, tile_path in enumerate(tile_paths):
        tile_id = tile_path.stem
        img = Image.open(tile_path).convert("RGB")
        arr = np.array(img)
        crops = make_crops(arr, crop_size=crop_size, n_crops=n_crops)

        crop_features = embed_crops(model, preprocess, crops, device=device)
        # Mean-pool across crops for this tile
        mean_feat = crop_features.mean(axis=0)
        mean_feat = mean_feat / (np.linalg.norm(mean_feat) + 1e-8)
        embeddings.append(mean_feat)

        meta.append({
            "tile_id": tile_id,
            "tile_path": str(tile_path),
            "n_crops": len(crops),
        })

        if (i + 1) % 50 == 0:
            elapsed = time.time() - t0
            print(f"[index_tiles] Embedded {i+1}/{len(tile_paths)} tiles ({elapsed:.1f}s)")

    embeddings_array = np.vstack(embeddings).astype("float32")
    embed_dim = embeddings_array.shape[1]
    print(f"[index_tiles] Building FAISS Flat-IP index, dim={embed_dim}, n={len(embeddings_array)}")

    index = faiss.IndexFlatIP(embed_dim)
    index.add(embeddings_array)

    index_path = output_dir / "skyclip.index"
    meta_path = output_dir / "skyclip_meta.json"

    faiss.write_index(index, str(index_path))

    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "embed_dim": embed_dim,
                "n_tiles": len(meta),
                "n_crops_per_tile": n_crops,
                "tiles": meta,
            },
            f,
            indent=2,
        )

    elapsed_total = time.time() - t0
    print(f"[index_tiles] Done. Index: {index_path}, Meta: {meta_path}")
    print(f"[index_tiles] Total time: {elapsed_total:.1f}s ({elapsed_total/len(tile_paths):.2f}s/tile)")

    # Update provenance.json
    prov_path = Path("data/provenance.json")
    if prov_path.exists():
        with open(prov_path, "r", encoding="utf-8") as f:
            prov = json.load(f)
    else:
        prov = {}
    prov["skyclip_index_built"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    prov["skyclip_index_n_tiles"] = len(meta)
    prov["skyclip_embed_dim"] = embed_dim
    prov["skyclip_arch"] = getattr(model, "_geolens_arch", "unknown")
    prov["skyclip_n_crops"] = n_crops
    prov["skyclip_index_time_s"] = round(elapsed_total, 1)
    with open(prov_path, "w", encoding="utf-8") as f:
        json.dump(prov, f, indent=2)
    print(f"[index_tiles] Updated {prov_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build SkyCLIP FAISS index from tiles.")
    parser.add_argument("--tiles-dir", type=Path, default=DEFAULT_TILES_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--n-crops", type=int, default=DEFAULT_N_CROPS)
    parser.add_argument("--crop-size", type=int, default=DEFAULT_CROP_SIZE)
    args = parser.parse_args()

    build_index(
        tiles_dir=args.tiles_dir,
        output_dir=args.output_dir,
        n_crops=args.n_crops,
        crop_size=args.crop_size,
    )
