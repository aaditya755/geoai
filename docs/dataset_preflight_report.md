# GeoLens AI — Dataset Preflight Report

Generated: 2026-10-09T14:23:04Z UTC  
Tiles dir: `data\raw\spacenet_rio`  
OSM dir: `data\raw\osm`  

> **Note:** This report reflects only what is actually present on disk.
> No file paths, feature counts, or coverage numbers are invented.

---

## 1. SpaceNet Imagery Tiles
**Directory not found:** `data\raw\spacenet_rio`

The SpaceNet Buildings v1 tiles have not been downloaded yet.
Run the manual download step (tasks.md P1.1) before proceeding with P1.

```
aws s3 cp s3://spacenet-dataset/spacenet/SN1_buildings/  data/raw/spacenet_rio/  --recursive
```

---

## 2. OpenStreetMap Data
**Directory not found:** `data\raw\osm`

OSM data has not been downloaded yet.
Run `data_prep.py` after downloading the SpaceNet tiles (P1.3).

---

## 3. Tile / OSM Coverage Overlap
`data/processed/tile_index.geojson` not found. Run `data_prep.py` first to build the tile index.

---

## 4. Missing Data, Limitations and Unsupported Concepts

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


---

## 5. Recommended P2 OSM-only Vertical Slice Query
**Cannot recommend a query yet** — OSM data not downloaded.

After running `data_prep.py`, re-run this script to get a data-driven recommendation.

**Default recommendation (subject to data availability):**

> `"primary roads within 500 m of the dataset boundary"`

Rationale: roads (`highway=*`) are the most reliably mapped OSM feature in urban Rio de Janeiro. A `dwithin` query exercises plan parsing, spatial filtering, measured_distance_m output, the API response schema, and map rendering — the full P2 vertical slice — without requiring any vision model inference.

**Confirm this choice after running data_prep.py and verifying that roads are present in the OSM extract.**
