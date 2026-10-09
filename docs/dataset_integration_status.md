# GeoLens AI — Dataset Integration Status

Last updated: 2026-10-09

---

## Download status

Downloads running via `python -c "..."` (background process, terminal `term_1791560000247_f7an8dyn1k`).

| File | Size | Status |
|------|------|--------|
| `SkyCLIP_ViT_B32_top50pct.zip` | 1,515 MB | **~73% complete, ~0.8 MB/s** |
| `SN1_buildings_train_AOI_1_Rio_3band.tar.gz` | 2,572 MB | Queued |
| `SN1_buildings_train_AOI_1_Rio_geojson_buildings.tar.gz` | 21 MB | Queued |

Monitor: `get_process_output` on terminal `term_1791560000247_f7an8dyn1k`

---

## Steps to complete after downloads finish

Run these commands in order:

### 1. Verify checkpoint extraction

```
python -c "
from pathlib import Path
pts = list(Path('data/embeddings').rglob('*.pt'))
print('Found .pt files:', pts)
"
```

Expected: at least one `.pt` file under `data/embeddings/SkyCLIP_ViT_B32_top50pct/`.

Update `.env`:
```
SKYCLIP_WEIGHTS=data/embeddings/SkyCLIP_ViT_B32_top50pct/<actual_filename>.pt
```

### 2. Verify SkyCLIP loads

```
python -c "
from skyclip_loader import load_skyclip, get_embed_dim
model, preprocess, tokenizer = load_skyclip()
print('embed_dim:', get_embed_dim(model))
print('arch:', model._geolens_arch)
"
```

Expected output:
```
[skyclip_loader] Loading ViT-B/32 (embed_dim=512) on cpu
[skyclip_loader] Model ready. embed_dim=512
embed_dim: 512
arch: ViT-B/32
```

### 3. Verify SpaceNet extraction

```
python -c "
from pathlib import Path
tiles = sorted(Path('data/raw/spacenet_rio/RGB-PanSharpen').glob('*.tif'))
print(f'{len(tiles)} tiles found')
print('Sample:', tiles[0].name if tiles else 'NONE')
geojsons = sorted(Path('data/raw/spacenet_rio/geojson').glob('*.geojson'))
print(f'{len(geojsons)} GeoJSON files found')
"
```

Expected: ~6,940 tiles, ~6,940 GeoJSON files (one per tile).

### 4. Run data_prep on 20-tile subset

```
python scripts/run_data_prep_subset.py --n-tiles 20
```

Expected: 20 stretched tiles in `data/processed/tiles_8bit/`, `data/provenance.json` created.

### 5. Run alignment checks

```
python scripts/check2_alignment.py
python scripts/check3_tile_meta.py
```

Both must pass before proceeding.

### 6. Extract test crops for check1

```
python scripts/extract_check_crops.py
```

Creates `data/crops/check1_pool_proxy.png` and `data/crops/check1_road_proxy.png`.

### 7. Run check1 — P3 gate

```
python scripts/check1_skyclip.py \
  --pool-crop data/crops/check1_pool_proxy.png \
  --road-crop data/crops/check1_road_proxy.png
```

**STOP HERE.** Record the similarity scores and wait for review before proceeding to P4.

Fill in `docs/phase_gate_report_template.md` with real values.

---

## Installed packages

| Package | Version | Status |
|---------|---------|--------|
| openai/CLIP | 1.0 | ✅ Installed |
| faiss-cpu | 1.15.1 | ✅ Installed |
| torchvision | 0.29.1 | ✅ Installed |
| torch | 2.14.1+cpu | ✅ (CPU only — no CUDA) |

---

## Known constraints

- **No CUDA on this machine** (`torch 2.14.1+cpu`). SkyCLIP ViT-B/32 on CPU:
  - Text embedding: ~0.5–2 s (acceptable)
  - Image embedding per crop: ~2–5 s (slow but feasible for 20-tile dev run)
  - FAISS indexing of all ~6,940 tiles: ~8–14 hrs on CPU — not practical
  - **Recommendation:** Use Colab/Kaggle for full indexing (P3.3 [MANUAL])
  - The check1 gate (P3.2) IS feasible on CPU with 2 crops

- **Domain gap not yet measured.** SkyCLIP was trained on globally diverse SkyScript imagery. SpaceNet Rio uses WorldView-3 satellite imagery. Cross-dataset similarity is unknown until check1 runs.

- **SpaceNet v1 Rio does not label swimming pools.** Building footprints only. The "pool_proxy" crop used in check1 is a building-dense tile — adequate for testing SkyCLIP's text-image alignment, not for validating pool detection specifically.

---

## Files changed/created this session

| File | Change |
|------|--------|
| `skyclip_loader.py` | Arch auto-detection (ViT-B/32 or ViT-L/14 from filename), correct embed_dim per arch, `get_embed_dim()`, `_find_default_weights()` |
| `index_tiles.py` | Added arch to provenance.json |
| `jev_ranker.py` | Added `JEV_ENABLED`, `JEV_API_ENDPOINT`, `JEV_MODEL` env var support; only dispatches to JevClient when `JEV_ENABLED=true AND JEV_API_KEY` set |
| `data_prep.py` | Fixed `glob("*.tif")` → `rglob("*.tif")` so SpaceNet `RGB-PanSharpen/` subdirectory is found |
| `scripts/check1_skyclip.py` | Added arch/embed_dim/device/CUDA reporting; machine-readable P3 gate fields |
| `scripts/download_datasets.py` | New — download with progress, skip if already complete |
| `scripts/post_download_setup.py` | New — automated P1–P3 sequence after downloads |
| `scripts/run_data_prep_subset.py` | New — run data_prep on N-tile subset with SpaceNet paths |
| `scripts/extract_check_crops.py` | New — extract 224×224 crops for check1 |
| `.env.example` | Updated SkyCLIP section |
| `tests/test_jev_ranker.py` | Added 2 tests for JEV_ENABLED/disabled behaviour |
| `docs/dataset_integration_status.md` | This file |
