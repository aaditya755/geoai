"""
check1_skyclip.py — verify SkyCLIP embedding similarity on toy crops.

This script is the P3 gate check. Run it on a GPU machine (Colab/Kaggle)
after the FAISS index is built to verify:
  1. Text-image similarity: the text "aerial view of a swimming pool" scores
     higher on pool crops than on road crops.
  2. Similarity threshold: pool-vs-pool cosine similarity > 0.2 (conservative).
  3. Pool-vs-road cosine similarity < pool-vs-pool similarity.

[MANUAL]: Run this script on a GPU machine after index_tiles.py completes.
Document the similarity scores in a comment or notebook before proceeding to P4.

Usage:
    python scripts/check1_skyclip.py [--pool-crop PATH] [--road-crop PATH]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

POOL_PROMPT = "aerial view of a swimming pool"
ROAD_PROMPT = "aerial view of a road or street"

# Minimum expected cosine similarity for correct text-image pair
MIN_POOL_SIMILARITY = 0.20
# Pool similarity must beat road similarity by at least this margin
MIN_MARGIN = 0.02


def run_check(pool_crop_path: Path, road_crop_path: Path) -> bool:
    """
    Run similarity checks.
    Returns True if all assertions pass, False otherwise.
    Prints results in a format suitable for docs/phase_gate_report_template.md.
    """
    from PIL import Image
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).parent.parent))
    from skyclip_loader import embed_crops, embed_text, get_device, load_skyclip

    print("[check1] Loading SkyCLIP model …")
    model, preprocess, tokenizer = load_skyclip()
    device = get_device()
    arch = getattr(model, "_geolens_arch", "unknown")
    import torch
    embed_dim = getattr(model, "_geolens_embed_dim", "unknown")
    print(f"[check1] Architecture: {arch}")
    print(f"[check1] Embed dim:    {embed_dim}")
    print(f"[check1] Device:       {device}")
    print(f"[check1] CUDA:         {torch.cuda.is_available()}")

    # Load crops
    pool_img = Image.open(pool_crop_path).convert("RGB")
    road_img = Image.open(road_crop_path).convert("RGB")

    # Embed images
    pool_feat = embed_crops(model, preprocess, [pool_img], device=device)[0]
    road_feat = embed_crops(model, preprocess, [road_img], device=device)[0]

    # Embed text prompts
    pool_text_feat = embed_text(model, tokenizer, POOL_PROMPT, device=device)
    road_text_feat = embed_text(model, tokenizer, ROAD_PROMPT, device=device)

    # Cosine similarities (features are already L2-normalised)
    pool_pool_sim = float(np.dot(pool_feat, pool_text_feat))
    pool_road_sim = float(np.dot(pool_feat, road_text_feat))
    road_road_sim = float(np.dot(road_feat, road_text_feat))
    road_pool_sim = float(np.dot(road_feat, pool_text_feat))

    print(f"\n[check1] Similarity results:")
    print(f"  pool crop  × pool text  : {pool_pool_sim:.4f}  (expected > {MIN_POOL_SIMILARITY})")
    print(f"  pool crop  × road text  : {pool_road_sim:.4f}")
    print(f"  road crop  × road text  : {road_road_sim:.4f}")
    print(f"  road crop  × pool text  : {road_pool_sim:.4f}")
    print(f"  margin (pool-pool - pool-road): {pool_pool_sim - pool_road_sim:.4f}  (expected > {MIN_MARGIN})")

    passed = True

    if pool_pool_sim < MIN_POOL_SIMILARITY:
        print(f"\n✗ FAIL: pool-pool similarity {pool_pool_sim:.4f} < threshold {MIN_POOL_SIMILARITY}")
        passed = False
    else:
        print(f"\n✓ PASS: pool-pool similarity {pool_pool_sim:.4f} ≥ threshold {MIN_POOL_SIMILARITY}")

    if pool_pool_sim - pool_road_sim < MIN_MARGIN:
        print(f"✗ FAIL: margin {pool_pool_sim - pool_road_sim:.4f} < required {MIN_MARGIN}")
        passed = False
    else:
        print(f"✓ PASS: margin {pool_pool_sim - pool_road_sim:.4f} ≥ required {MIN_MARGIN}")

    if passed:
        print("\n✓ ALL CHECKS PASSED — proceed with P3.4 (concepts.yaml) and P3.5 (vision.py instance path)")
        print("  Document these numbers before clearing the P3 gate.")
    else:
        print("\n✗ SOME CHECKS FAILED — review SkyCLIP weights and crops before proceeding.")
        print("  Decision required: (a) proceed, (b) add OWLv2 agreement, (c) pivot.")
        print("  See tasks.md P3.GATE.")

    # Machine-readable summary for phase gate report
    print(f"\n--- P3 GATE REPORT FIELDS ---")
    print(f"model_arch: {arch}")
    print(f"embed_dim: {embed_dim}")
    print(f"device: {device}")
    print(f"cuda_available: {torch.cuda.is_available()}")
    print(f"pool_pool_sim: {pool_pool_sim:.4f}")
    print(f"pool_road_sim: {pool_road_sim:.4f}")
    print(f"road_road_sim: {road_road_sim:.4f}")
    print(f"road_pool_sim: {road_pool_sim:.4f}")
    print(f"margin: {pool_pool_sim - pool_road_sim:.4f}")
    print(f"threshold_met: {pool_pool_sim >= MIN_POOL_SIMILARITY}")
    print(f"margin_met: {pool_pool_sim - pool_road_sim >= MIN_MARGIN}")
    print(f"all_passed: {passed}")
    print(f"pool_crop: {pool_crop_path}")
    print(f"road_crop: {road_crop_path}")
    print(f"--- END P3 GATE REPORT FIELDS ---")

    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SkyCLIP similarity check (P3 gate).")
    parser.add_argument("--pool-crop", type=Path, required=True,
                        help="Path to a 224x224 pool crop image")
    parser.add_argument("--road-crop", type=Path, required=True,
                        help="Path to a 224x224 road crop image")
    args = parser.parse_args()

    ok = run_check(args.pool_crop, args.road_crop)
    sys.exit(0 if ok else 1)
