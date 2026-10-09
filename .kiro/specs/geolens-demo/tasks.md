# GeoLens AI (GEOAI 05) — Tasks

Spec: geolens-demo  
Source of truth: docs/GEOAI05_SPEC_v2.md  

Phase rule: each phase ends in a demo-able outcome with passing tests.  
[MANUAL] = task requires human action; the agent must not fake it.

---

## Phase 0 — Contracts, types, steering check

**Demo-able outcome:** `pytest tests/test_types.py` passes; `validate_plan()` rejects an invalid plan.

- [ ] **P0.1** Create `.kiro/specs/geolens-demo/` spec files (requirements.md, design.md, tasks.md) ← *this file*
- [ ] **P0.2** Create `types.py` — Python type stubs (dataclasses or TypedDicts) for `Plan`, `Candidate`, `Result`, `ConceptKind` matching design.md §3 contracts
- [ ] **P0.3** Create `schemas/plan_schema.json` — JSON Schema for the plan object; wire into a `validate_plan(plan: dict) -> None` utility (raises `ValidationError` on failure)
- [ ] **P0.4** Create `tests/test_types.py` — verifies Plan round-trips through JSON and schema validation
- [ ] **P0.5** Verify `.kiro/steering/` files are up to date and reference `docs/GEOAI05_SPEC_v2.md`

---

## Phase 1 — Data subset + alignment checks

**Demo-able outcome:** `data_prep.py` runs on 10-tile subset; `provenance.json` exists; alignment check passes on sample.

- [ ] **P1.1** [MANUAL] Download SpaceNet Buildings v1 Rio de Janeiro subset from AWS S3:
  ```
  aws s3 cp s3://spacenet-dataset/spacenet/SN1_buildings/  data/raw/spacenet_rio/  --recursive
  ```
  Target: ~100 tiles for dev, full set for eval. Do not proceed with data-dependent tasks until this is done.
- [ ] **P1.2** Extend `data_prep.py` — add global brightness stretch (REQ-001): apply a single global percentile stretch (e.g. 2nd–98th percentile computed across all tiles) before saving 8-bit tiles to `data/processed/tiles_8bit/`
- [ ] **P1.3** Extend `data_prep.py` — add OSM intersection filter (REQ-002): compute bounding box as union of tile footprints; pass it to the Overpass/OSM download call; assert result bbox ± 10 m
- [ ] **P1.4** Extend `data_prep.py` — add provenance metadata output (REQ-003): write `data/provenance.json` with keys `osm_download_date`, `gdal_version`, `geopandas_version`, `python_version`
- [ ] **P1.5** [MANUAL] Run `scripts/check2_alignment.py` on processed tiles to verify pixel↔geo alignment
- [ ] **P1.6** [MANUAL] Run `scripts/check3_tile_meta.py` to verify tile metadata completeness
- [ ] **P1.7** Generate `data/processed/tile_index.geojson` from processed tile footprints (script or data_prep step)

---

## Phase 2 — Spatial engine + OSM-only vertical slice

**Demo-able outcome:** `POST /chat {"query": "roads within 200 m of the park"}` returns valid JSON from OSM data; UI shows results on map from fixture; GeoJSON export works.

- [ ] **P2.1** Create `spatial_engine.py` — implement `dwithin`, `intersects`, `negate` (feature-flagged FEATURE_NEGATE), all returning results with `measured_distance_m` column; all distances in EPSG:32723 (REQ-008, REQ-009, REQ-010, REQ-011)
- [ ] **P2.2** Create `tests/test_spatial_engine.py` — toy geometries in EPSG:32723; assert dwithin/intersects/negate results and measured_distance_m values
- [ ] **P2.3** Create minimal planner stub — hard-coded `osm_only` plan for "roads" to enable end-to-end test before full planner is built
- [ ] **P2.4** Create minimal `vision.py` stub — implement `osm_only` grounding path: lookup OSM GeoDataFrame, skip embedding model (REQ-007)
- [ ] **P2.5** Create `app.py` — FastAPI with `POST /chat` wired: stub planner → osm_only vision → spatial engine → passthrough ranker (REQ-012)
- [ ] **P2.6** Create `frontend/` scaffold — Vite + React, dark navy theme (#0B1020 / #121A33 / teal #2DD4BF / violet #8B5CF6 / pink #E0559A, Inter font); hard-code to `src/fixtures/demo_results.json`; show **"Sample data"** banner
- [ ] **P2.7** Wire frontend map component — display dashed bounding boxes and `measured_distance_m` from fixture (REQ-013)
- [ ] **P2.8** Implement GeoJSON export button — export FeatureCollection with confidence and measured_distance_m properties from fixture data (REQ-014)

---

## Phase 3 — SkyCLIP loader, check1, index, vision

**Demo-able outcome:** `skyclip_loader.py` loads model; toy FAISS test passes; check1 results documented.  
**⚠ GATE: STOP after this phase and wait for human review of check1 results before building Phase 4+.**

- [ ] **P3.1** Create `skyclip_loader.py` — load pretrained SkyCLIP weights; verify model loads without error; expose `embed_text(text: str) -> np.ndarray` and `embed_crop(img: np.ndarray) -> np.ndarray`
- [ ] **P3.2** [MANUAL — GPU] Run `scripts/check1_skyclip.py` on 10 toy crops to verify embedding similarity scores. Run on Colab or Kaggle GPU. Record results. **This gate determines whether to proceed with SkyCLIP-only, add OWLv2 agreement, or pivot.**
- [ ] **P3.3** [MANUAL — GPU] Run `index_tiles.py` on processed tiles to build FAISS index (`data/embeddings/skyclip.index`). Multi-crop (≥3 overlapping 224×224 crops per tile), mean-pooled embeddings (REQ-004). Record embedding time and index size in `data/provenance.json`.
- [ ] **P3.4** Create `concepts.yaml` registry — at minimum: `swimming_pool` (instance), `road` (osm_only), `building` (instance), `park` (osm_only); each entry has `kind`, `skyclip_text`, `osm_key`, `osm_value`, `description` (REQ-017)
- [ ] **P3.5** Implement `vision.py` instance grounding path — multi-crop SkyCLIP retrieval from FAISS; return DataFrame with columns [tile_id, bbox, score, concept_id] (REQ-004, REQ-005, REQ-006)
- [ ] **P3.6** Create `tests/test_vision_fixture.py` — toy FAISS index with known embeddings; assert top-K results are correct
- [ ] **P3.GATE** [MANUAL] STOP. Share `check1_skyclip.py` results with the team. Decision required:
  - (a) Proceed with SkyCLIP-only
  - (b) Add OWLv2 agreement (REQ-027 STRETCH)
  - (c) Pivot strategy
  
  **Do not build Phase 4+ until this gate is cleared.**

---

## Phase 4 — Planner adapter, sessions, follow-ups, PROPOSED fields

**Demo-able outcome:** Follow-up query ("now within 50 m") amends previous plan; golden query tests pass; PROPOSED fields are inert when flags off.

- [ ] **P4.1** Extend `planner_agent.py` — wire to `OpenRouterPlannerProvider` via `llm_provider.py` interface; implement fallback rule-based planner (REQ-015). The provider interface is in `llm_provider.py`; switching to another provider requires only implementing `LLMPlannerProvider` there.
- [ ] **P4.2** Extend `planner_agent.py` — implement session store (in-memory dict keyed by session_id) for follow-up queries
- [ ] **P4.3** Implement follow-up query amendment — planner receives previous plan + delta query; returns amended plan (see design.md §6.2)
- [ ] **P4.4** Implement `negate` spatial operation behind `FEATURE_NEGATE` flag (REQ-010) — confirm no other code path depends on it
- [ ] **P4.5** Implement `min_area_m2` filter behind `FEATURE_MIN_AREA` flag (REQ-026) — confirm no other code path depends on it
- [ ] **P4.6** Add ~40 golden queries to `tests/golden_queries.json`; write `tests/test_planner_golden.py` (REQ-024)
- [ ] **P4.7** [MANUAL] Obtain `OPENROUTER_API_KEY`; set `OPENROUTER_RUN_LIVE_TESTS=true`; run `pytest tests/test_llm_provider_live.py -v -s`. Record model used, whether structured output was accepted, and the raw plan returned (REQ-015 live integration path).

---

## Phase 5 — UI live mode, evidence, export

**Demo-able outcome:** Full pipeline from live query to map results; evidence thumbnails visible; attribution page reachable.

- [ ] **P5.1** Wire frontend `/chat` API call to live backend — replace fixture default; keep **"Sample data"** banner when `DEMO_MODE=true`
- [ ] **P5.2** Implement animated 4-step pipeline card — steps: Understanding → Searching imagery → Applying spatial rules → Ranking; each step activates as the backend reports progress
- [ ] **P5.3** Implement editable plan chips (REQ-020) — click to edit value, trigger re-run of affected pipeline step
- [ ] **P5.4** Implement evidence thumbnails tab (REQ-021) — 112×112 px crop centred on each candidate
- [ ] **P5.5** Implement right panel tabs: Results, Ranking (Jev AI), Evidence, Export
- [ ] **P5.6** Add buffer ring visualisation on map — draw ring at `distance_m` radius around selected result
- [ ] **P5.7** Create attribution page (REQ-016):
  - SpaceNet Buildings v1 — CC BY-SA 4.0 — arXiv:1807.01232
  - OpenStreetMap contributors — ODbL
  - SkyScript — arXiv:2312.12856

---

## Phase 6 — Jev ranking + translation adapters

**Demo-able outcome:** Ranking tab shows Jev AI scores with per-criterion breakdown; non-English query passes through (or translates if key available).

- [ ] **P6.1** Implement `jev_ranker.py` — `score_local` with weights (confidence=0.4, proximity=0.3, size=0.3) and per-criterion `score_breakdown` dict; `JevClient` stub interface (design.md §7.1)
- [ ] **P6.2** Wire `jev_ranker.py` into `/chat` pipeline; add Ranking tab in UI showing jev_score and score_breakdown per result
- [ ] **P6.3** Implement `translate.py` — `translate(text, from_lang, to_lang)` with Sarvam AI stub and passthrough fallback; mark `# TODO: verify Sarvam AI endpoint` (design.md §7.2)
- [ ] **P6.4** [MANUAL] Obtain `SARVAM_API_KEY`; verify Sarvam AI endpoint URL and request schema; replace TODO in translate.py
- [ ] **P6.5** Wire `translate.py` into `/chat` — detect non-English input, translate to English before planning, show English plan chips in UI

---

## Phase 7 — Eval, caching, Demo mode, README

**Demo-able outcome:** Full judge-ready demo; `eval.py` prints honest precision@K table; Demo mode works offline; README complete.

- [ ] **P7.1** Implement detection cache in `vision.py` — key: `(query_hash, tile_id)`; store/load from `data/cache/detections/`; log cache hit (REQ-022)
- [ ] **P7.2** [MANUAL] Hand-label ~100 crops for precision@K hold-out set; save to `data/annotations/labelled_crops.json`
- [ ] **P7.3** Implement `eval.py` — compute precision@K (K=5,10,20) over `data/annotations/labelled_crops.json`; print markdown table of results (REQ-023). Values must come from ground truth labels, not estimation.
- [ ] **P7.4** Implement Demo mode (`DEMO_MODE=true`) — serve `data/fixtures/demo_results.json`; show **"Sample data"** banner; all four pipeline steps complete from fixture (REQ-031 STRETCH)
- [ ] **P7.5** [MANUAL] Create `data/fixtures/demo_results.json` from a real successful run (not invented data)
- [ ] **P7.6** Create Guided demo stepper in UI — 4 steps matching the pipeline card; pre-loaded with demo query
- [ ] **P7.7** Write `README.md` with: project description, setup instructions, attribution block (see below), demo checklist
- [ ] **P7.8** Final demo checklist:
  - [ ] All MUST requirements (REQ-001 through REQ-016) pass
  - [ ] No invented numbers displayed in UI
  - [ ] **"Sample data"** label present wherever fixture data shown
  - [ ] Attribution page reachable from main UI
  - [ ] GeoJSON export produces a valid FeatureCollection
  - [ ] PROPOSED fields (negate, min_area_m2) are inert when flags off
  - [ ] `eval.py` prints real precision@K from ground truth
