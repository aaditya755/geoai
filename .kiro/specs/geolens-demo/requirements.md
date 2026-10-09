# GeoLens AI (GEOAI 05) — Requirements

Spec: geolens-demo  
Source of truth: docs/GEOAI05_SPEC_v2.md  
Format: EARS (Easy Approach to Requirements Syntax)  
Priority tags: MUST / SHOULD / STRETCH

---

## MUST Requirements (P0–P5)

### REQ-001 [MUST] Data prep — global brightness stretch
**EARS:** When data_prep.py is run on the Rio de Janeiro SpaceNet subset, the system shall apply a global brightness/contrast stretch across all tiles before saving.  
**Acceptance criteria:**
- Histogram of output tiles shows < 1% clipping at both ends.
- No per-tile normalisation applied independently.

### REQ-002 [MUST] Data prep — OSM intersection filter
**EARS:** When data_prep.py downloads OSM features, the system shall restrict downloads only to grid cells that intersect the imagery tiles bounding box, not the full municipality.  
**Acceptance criteria:**
- OSM GeoDataFrame bbox matches the union of tile footprints ± 10 m.

### REQ-003 [MUST] Data prep — provenance metadata
**EARS:** When data_prep.py completes a run, the system shall record the OSM download date, GDAL version, GeoPandas version, and Python version to data/provenance.json.  
**Acceptance criteria:**
- data/provenance.json exists and is a valid JSON object.
- Contains keys: osm_download_date, gdal_version, geopandas_version, python_version.

### REQ-004 [MUST] SkyCLIP multi-crop index
**EARS:** When index_tiles.py is run, the system shall embed each tile using at least three overlapping 224×224 crops per tile and store mean-pooled embeddings in the FAISS index.  
**Acceptance criteria:**
- Index file exists.
- Querying it with a text prompt returns tile_ids.
- Embedding dimension matches the model's output.

### REQ-005 [MUST] SkyCLIP retrieval
**EARS:** When a search query is issued, the system shall retrieve the top-K tiles from the FAISS index using cosine similarity and return ranked tile_ids with scores.  
**Acceptance criteria:**
- check1_skyclip.py passes its similarity threshold assertions on the toy fixture.

### REQ-006 [MUST] Concept grounding — instance kind
**EARS:** When the planner produces a concept of kind "instance", the vision engine shall run the SkyCLIP retrieval path and return candidates with tile_id, bbox, score columns.  
**Acceptance criteria:**
- vision.py returns a DataFrame with columns [tile_id, bbox, score, concept_id] for a "swimming pool" instance concept.

### REQ-007 [MUST] Concept grounding — osm_only kind
**EARS:** When the planner produces a concept of kind "osm_only", the system shall return matching OSM geometries directly, skipping vision model inference.  
**Acceptance criteria:**
- vision.py returns a GeoDataFrame from the OSM layer for a "road" osm_only concept without calling any embedding model.

### REQ-008 [MUST] Spatial engine — dwithin
**EARS:** When a spatial relation of type "dwithin" is evaluated, the spatial engine shall return only candidates whose geometry is within the specified distance (in metres) of the reference geometry, measured in a projected CRS.  
**Acceptance criteria:**
- spatial_engine.py unit tests pass on toy geometries.
- Distances are in metres (EPSG:32723 for Rio).

### REQ-009 [MUST] Spatial engine — intersects
**EARS:** When a spatial relation of type "intersects" is evaluated, the spatial engine shall return only candidates whose geometry intersects the reference geometry.  
**Acceptance criteria:**
- spatial_engine.py unit tests pass on toy geometries.

### REQ-010 [MUST] Spatial engine — negate (feature-flagged PROPOSED)
**EARS:** When a spatial relation of type "negate" is evaluated AND the FEATURE_NEGATE flag is enabled, the spatial engine shall return candidates that do NOT satisfy the inner relation.  
**Acceptance criteria:**
- negate unit test passes.
- Flag defaults to False.
- No other code path depends on it until the team agrees.

### REQ-011 [MUST] Spatial engine — measured distances
**EARS:** When the spatial engine returns results, each result row shall include a measured_distance_m column containing the actual computed distance in metres.  
**Acceptance criteria:**
- Result DataFrame contains measured_distance_m.
- Values are finite floats ≥ 0.

### REQ-012 [MUST] /chat API endpoint
**EARS:** When a POST request is made to /chat with a JSON body {query, session_id?}, the system shall return a JSON response containing plan, candidates, and ranked_results.  
**Acceptance criteria:**
- curl test returns HTTP 200 with a valid JSON body matching the response schema in design.md §3.

### REQ-013 [MUST] Map UI — bounding boxes
**EARS:** When results are displayed on the map, the system shall render a dashed bounding box for each candidate overlaid on the basemap tile.  
**Acceptance criteria:**
- Playwright/manual check confirms bounding boxes visible on the map component for fixture data.

### REQ-014 [MUST] GeoJSON export
**EARS:** When the user clicks Export on the results panel, the system shall download a valid GeoJSON FeatureCollection containing all current result geometries and their properties.  
**Acceptance criteria:**
- Exported file passes geojson-validation.
- Features include confidence and measured_distance_m properties.

### REQ-015 [MUST] OpenRouter planner — real call + fallback
**EARS:** When OPENROUTER_API_KEY is set, the system shall call the OpenRouter API with the configured model to produce the plan JSON; when the key is absent or the call fails, the system shall fall back to a local rule-based planner.  
**Acceptance criteria:**
- Integration test with a real key and configured model returns a schema-valid plan (`tests/test_llm_provider_live.py`, opt-in).
- Unit test with key unset exercises the fallback and also returns a schema-valid plan (`tests/test_llm_provider.py`).
- Provider response that fails local schema validation triggers fallback; invalid output is never returned.
- API key never appears in the plan JSON, session history, or any response returned to the client.

### REQ-016 [MUST] Attribution page
**EARS:** The UI shall include an accessible attribution page listing SpaceNet Buildings v1 (CC BY-SA 4.0, arXiv:1807.01232), OpenStreetMap contributors (ODbL), and SkyScript (arXiv:2312.12856).  
**Acceptance criteria:**
- Attribution page is reachable from the main UI.
- All three sources are listed with correct licence identifiers.

---

## SHOULD Requirements (P3–P6)

### REQ-017 [SHOULD] concepts.yaml registry
**EARS:** The system should maintain a concepts.yaml file mapping concept names to kind, skyclip_text, osm_key, osm_value, and description fields.  
**Acceptance criteria:**
- concepts.yaml validates against the schema defined in design.md.
- skyclip_loader.py reads it at startup.

### REQ-018 [SHOULD] roof_attr classifier
**EARS:** The system should classify detected building roofs into material categories using a lightweight classifier on RGB crops.  
**Acceptance criteria:**
- roof_attr.py returns a label and confidence for a given crop.
- Accuracy measured on labelled hold-out set is reported honestly.

### REQ-019 [SHOULD] road_attr classifier
**EARS:** The system should classify road segments by class (residential, primary, etc.) using OSM tags.  
**Acceptance criteria:**
- road_attr.py returns OSM highway tag value for a given road geometry.
- Returns "unknown" when tag absent.

### REQ-020 [SHOULD] Editable plan chips
**EARS:** The UI should allow the user to click a plan chip and edit its value (e.g. change distance threshold), triggering a re-run of the affected pipeline step.  
**Acceptance criteria:**
- Editing a distance chip updates the plan JSON and re-renders results.

### REQ-021 [SHOULD] Evidence thumbnails
**EARS:** The system should display a 112×112 px image crop centred on each detected candidate in the Evidence tab.  
**Acceptance criteria:**
- Evidence tab shows at least one thumbnail per result for fixture data.

### REQ-022 [SHOULD] Detection cache
**EARS:** The system should cache vision model outputs keyed by (query_hash, tile_id) to avoid re-running embeddings on repeated queries.  
**Acceptance criteria:**
- Second identical query returns in < 500 ms.
- Cache hit logged.

### REQ-023 [SHOULD] Precision@K evaluation
**EARS:** The system should compute precision@K (K=5,10,20) over labelled hold-out annotations and report results in eval.py output.  
**Acceptance criteria:**
- eval.py prints a markdown table of precision@K values.
- Values are computed from ground truth, not estimated.

### REQ-024 [SHOULD] Golden planner queries (~40)
**EARS:** The system should include approximately 40 golden (query, expected_plan_fragment) pairs in tests/golden_queries.json for regression testing.  
**Acceptance criteria:**
- pytest test_planner_golden.py passes.
- Test fails loudly on schema violations.

### REQ-025 [SHOULD] Equivalent SQL label
**EARS:** When the UI displays an "equivalent SQL" expression, it should be labelled "Equivalent (not executed)" unless the team has verified actual SQL execution.  
**Acceptance criteria:**
- UI label text matches exactly.
- No code path executes the SQL string.

### REQ-026 [SHOULD] min_area_m2 filter (feature-flagged PROPOSED)
**EARS:** The system should support a target.filters.min_area_m2 field in the plan schema when FEATURE_MIN_AREA flag is enabled, filtering candidates below the stated area.  
**Acceptance criteria:**
- Unit test passes.
- Flag defaults to False.
- Documented in design.md as PROPOSED.

---

## STRETCH Requirements (P7)

### REQ-027 [STRETCH] OWLv2 + SkyCLIP agreement
**EARS:** The system may run OWLv2 open-vocabulary detection in parallel with SkyCLIP and return only candidates that agree between both models.  
**Acceptance criteria:**
- Configurable agreement threshold.
- Accuracy delta reported vs SkyCLIP-only.

### REQ-028 [STRETCH] Area-window classification
**EARS:** The system may classify candidates by area range (e.g. small / medium / large) using polygon area from the spatial engine output.  
**Acceptance criteria:**
- area_class column present in result DataFrame when feature enabled.

### REQ-029 [STRETCH] /chat/stream SSE endpoint
**EARS:** The system may expose /chat/stream returning server-sent events for each pipeline step completion.  
**Acceptance criteria:**
- Browser EventSource receives at least 4 events per query (one per pipeline step).

### REQ-030 [STRETCH] Distance slider re-run
**EARS:** The UI may expose a distance slider that re-runs only the spatial engine step (not vision) when the threshold changes.  
**Acceptance criteria:**
- Slider drag triggers only a /spatial call.
- Vision results are reused from cache.

### REQ-031 [STRETCH] Offline / Demo mode
**EARS:** The system may serve a "Demo mode" from a local JSON fixture so the demo works without any API keys or GPU.  
**Acceptance criteria:**
- Demo mode flag in .env.
- UI shows "Sample data" banner.
- All four pipeline steps complete from fixture.

---

## CUT — Do not build

The following are explicitly out of scope:
- GeoGround
- Any agent framework (LangChain, AutoGPT, etc.)
- Fine-tuning of any model
- Authentication or user databases
- SAM 3
- FarSLIP
- opengeos/geoai as a runtime dependency
