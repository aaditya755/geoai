# GeoLens AI — P3 Gate Report

**Date:** 2026-10-09  
**Status: FAILED — awaiting team decision before P4**

---

## 1. Check results (actual execution)

### check2_alignment.py
```
✓ ALL ALIGNMENT CHECKS PASSED (20 tiles)
```
All 20 processed tiles: pixel↔geo alignment within tolerance.

### check3_tile_meta.py
```
✓ provenance.json: all required keys present
✓ ALL METADATA CHECKS PASSED (20 tiles)
```

### check1_skyclip.py (P3 gate)
```
pool crop  × pool text  : 0.2232   (threshold > 0.20 → PASS)
pool crop  × road text  : 0.2310
road crop  × road text  : 0.2953
road crop  × pool text  : 0.2829
margin (pool-pool − pool-road): -0.0077   (required > 0.02 → FAIL)
```
**Overall: FAILED** — pool text does not score higher than road text on the "pool" crop.

---

## 2. P3 gate fields (machine-readable)

| Field | Value |
|-------|-------|
| model_arch | ViT-B/32 |
| embed_dim | 512 |
| device | cpu |
| cuda_available | False |
| pool_pool_sim | 0.2232 |
| pool_road_sim | 0.2310 |
| road_road_sim | 0.2953 |
| road_pool_sim | 0.2829 |
| margin | -0.0077 |
| threshold_met | True |
| margin_met | **False** |
| all_passed | **False** |
| pool_crop | data/crops/check1_pool_proxy.png |
| road_crop | data/crops/check1_road_proxy.png |

---

## 3. Verified facts (measured from real data)

| Item | Value | Notes |
|------|-------|-------|
| SpaceNet tiles | 6,940 | `data/raw/spacenet_rio/3band/` |
| Tile CRS | **EPSG:4326** (WGS84) | Not EPSG:32723 — see §4 |
| Tile size | 438×406 px | ~0.50 m/px estimated |
| Tile bands | 3 (RGB), uint8 | |
| Tile bounds | Rio de Janeiro ~-43.8°W, -22.9°S | ✓ correct AOI |
| GeoJSON labels | 6,940 | Building footprints per tile |
| SkyCLIP checkpoint | `SkyCLIP_ViT_B32_top50pct/epoch_20.pt` | 1,816 MB, epoch 20 |
| SkyCLIP arch | ViT-B/32 | 512-dim, ~6.7s load on CPU |
| Text embed time | ~0.08s per prompt | CPU |
| Image embed time | ~1–2s per crop | CPU (estimated) |
| CLIP base weights | `~/.cache/clip/ViT-B-32.pt` (337.6 MB) | Downloaded automatically |

---

## 4. Resolved assumptions from design.md §8

| # | Assumption | Resolution |
|---|-----------|------------|
| 1 | ~0.5 m/px | **Confirmed ~0.50 m/px** from tile dimensions and bounds |
| 5 | EPSG:32723 for Rio | **REFUTED — tiles are EPSG:4326 (WGS84)**. spatial_engine.py uses EPSG:32723 for distance calculations, which requires reprojection from tile CRS. data_prep must reproject tiles to EPSG:32723 before spatial ops. |

**Action required:** The tile CRS is WGS84, not UTM. `spatial_engine.py` correctly reprojects GeoDataFrames to EPSG:32723 before computing distances — no change needed there. However `data_prep.py` and `index_tiles.py` should note that tiles must be reprojected when computing areas or distances. The FAISS index uses pixel-space bboxes, not projected coords, so indexing is unaffected.

---

## 5. Analysis of check1 failure

**What the numbers mean:**

The pool crop (tile `3band_AOI_1_RIO_img10`) scores 0.2232 against "aerial view of a swimming pool" and 0.2310 against "aerial view of a road or street". The road text prompt scores *slightly higher* on the pool-proxy crop.

**Likely causes:**

1. **Wrong crop content.** The "pool proxy" is a building-dense tile, not a tile with a pool. SpaceNet v1 Rio does not label pools — the crop selection was heuristic. The tile selected may contain roads/streets and no pool-like features, making the road prompt legitimately higher.

2. **Domain gap.** SkyCLIP ViT-B/32 was trained on globally-diverse SkyScript imagery at various resolutions. SpaceNet Rio uses WorldView-3 at ~0.5 m/px. The model may not have strong discriminative signal for Rio-style urban tiles.

3. **ViT-B/32 vs ViT-L/14.** The smaller model (53.02% avg accuracy) may not discriminate well at this spatial scale and scene complexity. ViT-L/14 (59.91%) might show better margin.

4. **Threshold sensitivity.** pool_pool_sim (0.2232) barely exceeds the threshold (0.20). Both crops score ~0.22–0.29 for both prompts — the model is not strongly discriminating on these particular tiles.

**What is NOT failed:**

- The model loads correctly ✓
- Text embeddings are properly normalised ✓  
- The FAISS retrieval pipeline itself is unaffected — this tests *discriminative margin*, not retrieval correctness.

---

## 6. Decision required (choose one)

☐ **(a) Proceed as-is** — Accept that ViT-B/32 has limited discriminative margin on SpaceNet Rio. Use cosine similarity ranking (not hard thresholds) for retrieval. The pipeline can still return the most-similar tiles; it cannot guarantee high precision.

☐ **(b) Test ViT-L/14** — Download `SkyCLIP_ViT_L14_top30pct.zip` (4.4 GB) and repeat check1 on a GPU. ViT-L/14 has higher published accuracy (59.91% vs 53.02%). Requires Colab/Kaggle.

☐ **(c) Better crop selection** — Re-run check1 with crops hand-picked to contain visually distinct pool vs road content. The current crops were selected heuristically with no labelled pool tiles. Better crops might pass the margin check.

☐ **(d) Reduce threshold** — Lower `MIN_MARGIN` from 0.02 to 0.0 and proceed. This acknowledges that SkyCLIP's text-image alignment on SpaceNet Rio is weak but that ranking by similarity score is still useful.

☐ **(e) Pivot** — Use a different retrieval approach (e.g. OSM-only for all concepts, or a different vision model).

---

## 7. What must NOT proceed until decision is made

- P4 (planner sessions, follow-ups) — can proceed, no dependency on vision
- P4 vision features (instance grounding on real tiles) — **BLOCKED until gate cleared**
- P5 (UI live mode with real vision results) — **BLOCKED**
- P6 (evidence thumbnails from real tiles) — **BLOCKED**

---

## 8. Recommended next step

Run check1 again with **Option (c)** first (hand-picked crops):

```bash
# Pick a tile that actually contains a pool-like feature if one exists
# Or use any tile with clearly blue rectangular structures
# Then:
python scripts/check1_skyclip.py \
  --pool-crop data/crops/YOUR_POOL_CROP.png \
  --road-crop data/crops/YOUR_ROAD_CROP.png
```

If still failing, test ViT-L/14 on Colab (**Option b**) before deciding whether to proceed.

**Do not start P4 vision work until this gate is cleared.**
