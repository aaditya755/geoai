# GeoLens AI (GEOAI 05)

Natural-language search over aerial tiles and OpenStreetMap vectors for one municipality — SpaceNet Buildings v1, Rio de Janeiro.

**Principle:** The LLM writes only a schema-validated JSON plan. Vision models find candidates. Deterministic GeoPandas code applies spatial rules. Nothing geometric is decided by an LLM.

---

## Honesty rules

- Never invent OSM keys, column names, file paths, or accuracy numbers.
- Report only numbers the code measures.
- Mark every unverified assumption in `docs/design.md §8`.
- Answer "not found" honestly (solar panels, narrow drains are too small at ~0.5 m/px).
- All sample or fixture data shown in the UI is labelled **"Sample data"**.
- Local weighted scorer is labelled **"Local ranking"**, not "Jev AI". Jev AI is shown only after a real, successful API call.
- Passthrough translation is labelled as a fallback.
- Cached results are labelled as **cached**, not fresh inferences.

---

## Project structure

```
geo2/
  app.py                  FastAPI backend (/chat, /export, /attribution)
  llm_provider.py         LLMPlannerProvider interface + OpenRouterPlannerProvider
  planner_agent.py        OpenRouter → plan JSON (+ rule-based fallback)
  vision.py               SkyCLIP FAISS retrieval (instance) + OSM lookup (osm_only)
  spatial_engine.py       dwithin / intersects / negate (projected, metres)
  jev_ranker.py           Local weighted scorer + JevClient stub
  translate.py            Sarvam AI stub + passthrough fallback
  data_prep.py            Tile brightness stretch + OSM download + provenance
  index_tiles.py          Build FAISS index (GPU, MANUAL)
  skyclip_loader.py       SkyCLIP model loader
  eval.py                 precision@K evaluation
  validate_plan.py        JSON schema validation utility
  types.py                Shared Python type definitions
  concepts.yaml           Concept registry (kind, skyclip_text, osm_key)

  schemas/
    plan_schema.json      JSON Schema for plan validation

  docs/
    GEOAI05_SPEC_v2.md    Source of truth (placeholder — expand as project develops)
    design.md             Architecture, contracts, sequence diagrams
    semantics.md          Exact meanings of all spatial/plan operations
    phase_gate_report_template.md

  scripts/
    dataset_preflight.py  Inspect actual data on disk before P1
    check1_skyclip.py     SkyCLIP similarity gate check (P3, GPU)
    check2_alignment.py   Pixel↔geo alignment verification
    check3_tile_meta.py   Tile metadata completeness check

  tests/
    test_types.py         Plan round-trip + schema validation (P0 gate)
    test_spatial_engine.py  Spatial ops on toy geometries (P2 gate)
    test_planner.py       Fallback planner unit tests
    test_planner_golden.py  ~40 golden query regression tests
    test_jev_ranker.py    Ranker unit tests
    test_vision_fixture.py  Vision grounding on toy FAISS index
    golden_queries.json   Golden query/plan pairs

  frontend/               Vite + React UI (dark navy, map-first)
    src/
      api/                types.ts, client.ts
      components/         TopBar, ChatPanel, MapPanel, ResultsPanel, PlanChips, PipelineCard
      fixtures/           demoResults.ts (Sample data)
      pages/              AttributionPage

  data/                   (git-ignored)
    raw/spacenet_rio/     SpaceNet tiles [MANUAL download]
    raw/osm/              OSM parquet files
    processed/            8-bit stretched tiles, tile_index.geojson
    embeddings/           FAISS index [MANUAL GPU build]
    cache/                Detection cache
    fixtures/             demo_results.json (real cached run, MANUAL)
    annotations/          labelled_crops.json [MANUAL]
    provenance.json       Data prep audit trail
```

---

## Setup

### 1. Python environment

```bash
pip install -r requirements.txt
# For CLIP: pip install git+https://github.com/openai/CLIP.git
# GDAL: install via conda or system package manager (version must match system GDAL)
```

### 2. Environment variables

```bash
cp .env.example .env
# Edit .env and fill in API keys as needed
```

### LLM Planner — OpenRouter

The planner uses OpenRouter's OpenAI-compatible API. No provider-specific packages needed — only `requests`.

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Required for live inference. Get at [openrouter.ai/keys](https://openrouter.ai/keys) |
| `OPENROUTER_MODEL` | `google/gemini-2.0-flash-001` | Model identifier. Free alternative: `google/gemini-2.0-flash-exp:free` (rate-limited) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | Optional override |
| `OPENROUTER_TIMEOUT_S` | `30` | Request timeout (seconds) |
| `OPENROUTER_MAX_RETRIES` | `2` | Retries on 429/5xx |

Without `OPENROUTER_API_KEY`, the deterministic rule-based fallback planner is used automatically.  
To run the live integration test: `OPENROUTER_API_KEY=sk-or-... OPENROUTER_RUN_LIVE_TESTS=true pytest tests/test_llm_provider_live.py -v -s`

See `tasks.md` for the full task list. Manual steps:

**P1.1 — Download SpaceNet tiles:**
```bash
aws s3 cp s3://spacenet-dataset/spacenet/SN1_buildings/ data/raw/spacenet_rio/ --recursive
```

**P1 — Run data prep:**
```bash
python data_prep.py --subset 10   # dev subset (10 tiles)
python data_prep.py               # full run
```

**P1 — Run alignment checks:**
```bash
python scripts/check2_alignment.py
python scripts/check3_tile_meta.py
```

**P3.3 — Build FAISS index (GPU required — Colab/Kaggle):**
```bash
python index_tiles.py
```

**P3.2 — Run SkyCLIP similarity gate check:**
```bash
python scripts/check1_skyclip.py --pool-crop path/to/pool.png --road-crop path/to/road.png
```
⚠ **STOP after P3 and wait for user review before proceeding to P4.**

### 4. Run backend

```bash
uvicorn app:app --reload --port 8000
```

Demo mode (no GPU, no API keys needed):
```bash
DEMO_MODE=true uvicorn app:app --port 8000
```

### 5. Run frontend

```bash
cd frontend
npm install
npm run dev
```

### 6. Run tests

```bash
pytest tests/test_types.py tests/test_spatial_engine.py tests/test_planner.py tests/test_jev_ranker.py -v
```

---

## Dataset preflight

Before P1, inspect what's actually on disk:
```bash
python scripts/dataset_preflight.py
```
Report saved to `docs/dataset_preflight_report.md`. No data is invented.

---

## CUT list (do not build)

The following are explicitly out of scope:

- GeoGround
- Agent frameworks (LangChain, AutoGPT, etc.)
- Fine-tuning of any model
- Authentication or user databases
- SAM 3
- FarSLIP
- opengeos/geoai as a runtime dependency

---

## Feature flags (PROPOSED — off by default)

| Flag | Default | Description |
|------|---------|-------------|
| `FEATURE_NEGATE` | `false` | Enable `relations[].negate` spatial op |
| `FEATURE_MIN_AREA` | `false` | Enable `target.filters.min_area_m2` filter |
| `DEMO_MODE` | `false` | Serve fixture data, show "Sample data" |

See `docs/semantics.md` for exact semantics of both proposed fields.

---

## Data attribution

| Dataset | Licence | Citation |
|---------|---------|----------|
| **SpaceNet Buildings v1 (Rio de Janeiro)** | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Van Etten et al., [arXiv:1807.01232](https://arxiv.org/abs/1807.01232) |
| **OpenStreetMap** | [ODbL](https://opendatacommons.org/licenses/odbl/) | © OpenStreetMap contributors |
| **SkyScript** | See arXiv | Wang et al., [arXiv:2312.12856](https://arxiv.org/abs/2312.12856) |

Map tiles: © [CARTO](https://carto.com/) (CC BY 3.0), data © OpenStreetMap contributors, ODbL.

---

## Unverified assumptions

See `docs/design.md §8` for the full list. Key items:

1. SpaceNet v1 Rio pixel resolution is ~0.5 m/px — **unverified, confirm from tile metadata**
2. Sarvam AI translate endpoint URL — **unverified, see `translate.py` TODO**
3. Jev AI ranking API schema — **stub only**
4. EPSG:32723 is appropriate for Rio — **unverified, confirm from tile CRS header**

---

## Demo checklist (P7.8)

- [ ] All MUST requirements (REQ-001 – REQ-016) pass
- [ ] No invented numbers in UI
- [ ] "Sample data" label present wherever fixture data shown
- [ ] Attribution page reachable from main UI
- [ ] GeoJSON export produces a valid FeatureCollection
- [ ] PROPOSED fields (negate, min_area_m2) are inert when flags off
- [ ] `eval.py` prints real precision@K from ground truth labels
- [ ] `data/provenance.json` exists with all required keys
