# GeoLens AI (GEOAI 05)

**Natural-language search over aerial imagery and OpenStreetMap (OSM)
vectors for one municipality.**

GeoLens AI is scoped around **SpaceNet Buildings v1 imagery for Rio de
Janeiro**, with OSM vectors used for contextual features where
available.

> **Core principle:** The LLM writes only a schema-validated JSON plan.
> Vision components retrieve candidates. Deterministic GeoPandas/Shapely
> code applies spatial rules. The LLM does not decide geometry,
> distances, or intersections.

## Overview

The intended workflow lets a user ask a geospatial question in plain
language, converts it into a structured plan, retrieves image/vector
candidates, applies deterministic spatial operations, displays results
on an interactive map, and exports them as GeoJSON.

Example queries: - "Find buildings within 500 metres of a park." - "Show
buildings intersecting this area." - "Find places matching this visual
concept."

Supported query types depend on the current planner, concept registry,
available data/indexes, and enabled feature flags.

## Technical approach

1.  **User query** --- a user asks a question in the map UI.
2.  **Planner agent** --- converts the question into a schema-validated
    JSON plan; a deterministic rule-based fallback is available.
3.  **Vision/vector retrieval** --- retrieves candidates from imagery
    indexes and/or OSM data, depending on the query and available
    artifacts.
4.  **Spatial engine** --- applies deterministic distance, intersection,
    and other supported operations.
5.  **Map results** --- returns locations, geometry, and available
    measurements to the UI.
6.  **Optional ranking** --- local ranking may order candidates. Jev AI
    is shown as active only after a real successful API call.
7.  **Human review and refinement** --- users inspect results and refine
    their query.
8.  **Export** --- results can be returned as a GeoJSON
    FeatureCollection.

## Technology stack

The table below reflects the project's stated stack and target
architecture. **A technology appearing here does not mean every
integration is fully implemented or enabled.** See [Implementation
status and limitations](#implementation-status-and-limitations).

  -----------------------------------------------------------------------
  Layer                               Technologies
  ----------------------------------- -----------------------------------
  Frontend                            React 19, TypeScript, Vite,
                                      Tailwind CSS, MapLibre GL JS

  Backend and query planning          FastAPI, Pydantic v2, structured
                                      query parser, JSON Schema
                                      validation

  AI and language                     Sarvam Saaras v4, Sarvam-105B;
                                      optional Jev AI decision routing

  Semantic image search               SkyCLIP / SkyScript, pgvector, OWL
                                      v2

  Object detection and segmentation   Grounding DINO, SAM 2 / SAMGeo,
                                      OpenGeoAI

  Imagery and OSM ingestion           GDAL, Rasterio, Pyrosm, STAC
                                      metadata

  Geospatial intelligence             PostgreSQL, PostGIS, GeoPandas,
                                      Shapely, PyProj

  Storage and cache                   COG/GeoTIFF, S3-compatible storage,
                                      Redis

  Background jobs                     Celery, separate CPU/GPU inference
                                      workers

  Maps and raster serving             MapLibre GL JS, TiTiler

  Outputs and validation              GeoJSON, CSV, GeoParquet; SpaceNet
                                      Buildings v1 and locally labelled
                                      data

  Deployment                          Docker Compose; AWS optional
  -----------------------------------------------------------------------

## Repository structure

``` text
geo2/
├── app.py                    # FastAPI endpoints: /chat, /export, /attribution
├── llm_provider.py           # Planner provider interface and OpenRouter provider
├── planner_agent.py          # LLM planning with rule-based fallback
├── validate_plan.py          # Plan validation utility
├── vision.py                 # SkyCLIP/FAISS retrieval and OSM lookup paths
├── spatial_engine.py         # Deterministic spatial operations
├── jev_ranker.py             # Local weighted scorer and Jev client stub
├── translate.py              # Translation integration stub and fallback
├── data_prep.py              # Imagery preparation, OSM download and provenance
├── index_tiles.py            # Manual FAISS index build
├── skyclip_loader.py         # SkyCLIP model loader
├── eval.py                   # Precision@K evaluation
├── concepts.yaml             # Concept registry
├── types.py                  # Shared Python types
├── schemas/
│   └── plan_schema.json      # JSON Schema for plans
├── scripts/
│   ├── dataset_preflight.py
│   ├── check1_skyclip.py
│   ├── check2_alignment.py
│   └── check3_tile_meta.py
├── tests/                    # Unit, regression, planner and vision tests
├── docs/                     # Specification, design, semantics and gate reports
└── frontend/
    └── src/
        ├── api/
        ├── components/
        ├── fixtures/
        └── pages/
```

Additional demo fixtures, audit reports, and regression tests may exist
in the current checkout.

## Data layout

Large datasets, generated indexes, model weights, and caches are
intentionally kept outside Git.

``` text
data/
├── raw/
│   ├── spacenet_rio/          # SpaceNet imagery; manual download
│   └── osm/                   # OSM extracts / Parquet files
├── processed/                 # Prepared tiles and tile metadata
├── embeddings/                # FAISS index; manual GPU build
├── cache/                     # Detection/result cache
├── fixtures/                  # Optional cached demo results
├── annotations/               # Local evaluation labels
└── provenance.json            # Data-preparation audit trail
```

Do not assume these files exist merely because they are listed here. Run
the preflight script to inspect the actual local dataset state.

## Requirements

-   Python compatible with the pinned dependencies in
    `requirements.txt`.
-   Node.js and npm for the frontend.
-   Git.
-   API credentials only for integrations that are enabled.
-   GPU access for the documented manual SkyCLIP/FAISS index build; demo
    mode is intended to run without a GPU.

GDAL and its Python bindings may require a system or Conda installation
compatible with your environment.

## Setup

### 1. Create a Python environment

``` bash
python -m venv .venv
```

Activate it:

**Windows PowerShell**

``` powershell
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux**

``` bash
source .venv/bin/activate
```

Install dependencies:

``` bash
pip install -r requirements.txt
```

If the selected SkyCLIP workflow requires OpenAI CLIP, the project notes
this additional install:

``` bash
pip install git+https://github.com/openai/CLIP.git
```

### 2. Configure environment variables

**Windows PowerShell**

``` powershell
Copy-Item .env.example .env
```

**macOS / Linux**

``` bash
cp .env.example .env
```

Add only the credentials needed for integrations you intend to run.
Never commit `.env`, embed API keys in source code, or share keys in
logs/screenshots.

### OpenRouter planner configuration

The planner uses OpenRouter's OpenAI-compatible API through `requests`.

  -----------------------------------------------------------------------
  Variable                            Purpose
  ----------------------------------- -----------------------------------
  `OPENROUTER_API_KEY`                Enables live planner inference

  `OPENROUTER_MODEL`                  OpenRouter model identifier

  `OPENROUTER_BASE_URL`               API base URL; usually
                                      `https://openrouter.ai/api/v1`

  `OPENROUTER_TIMEOUT_S`              Request timeout in seconds

  `OPENROUTER_MAX_RETRIES`            Retry limit for eligible failures

  `OPENROUTER_RUN_LIVE_TESTS`         Opt-in switch for live integration
                                      tests
  -----------------------------------------------------------------------

Use `.env.example` as the source of truth for the defaults in this
checkout. Without an API key, the deterministic fallback planner should
be used where supported. A fallback response is not evidence that live
LLM inference succeeded.

If `tests/test_llm_provider_live.py` exists in this checkout, run the
live test only when you intend to make a real API request:

``` bash
OPENROUTER_API_KEY=your-key OPENROUTER_RUN_LIVE_TESTS=true pytest tests/test_llm_provider_live.py -v -s
```

In PowerShell, set variables first with
`$env:OPENROUTER_API_KEY = "..."`.

### 3. Inspect the dataset

``` bash
python scripts/dataset_preflight.py
```

The script is intended to inspect files actually present and write
`docs/dataset_preflight_report.md`. Missing files must be reported as
missing, not inferred to exist.

### 4. Prepare data

Download SpaceNet Buildings v1 imagery using the dataset's current
instructions and place it under `data/raw/spacenet_rio/`.

Run a small development subset first:

``` bash
python data_prep.py --subset 10
```

For the full preparation workflow:

``` bash
python data_prep.py
```

Review the generated provenance and verify tile metadata before relying
on image-derived coordinates.

### 5. Run alignment and metadata checks

``` bash
python scripts/check2_alignment.py
python scripts/check3_tile_meta.py
```

### 6. Build the image index (manual GPU workflow)

``` bash
python index_tiles.py
```

This may require a GPU environment such as Colab or Kaggle. A loaded
model or generated index alone does not establish retrieval accuracy.

### 7. Run the SkyCLIP gate check

``` bash
python scripts/check1_skyclip.py --pool-crop path/to/pool.png --road-crop path/to/road.png
```

**Stop after P3 and review the gate results before proceeding to P4.**

## Run the application

### Backend

From the repository root:

``` bash
uvicorn app:app --reload --port 8000
```

Demo mode is intended to run without GPU access or API keys.

**Windows PowerShell**

``` powershell
$env:DEMO_MODE = "true"
uvicorn app:app --reload --port 8000
```

**macOS / Linux**

``` bash
DEMO_MODE=true uvicorn app:app --reload --port 8000
```

Actual behavior depends on the current implementation and available
fixtures. Fixture/demo results must be labelled **"Sample data"** in the
UI.

### Frontend

Open a second terminal:

``` bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. Ensure the frontend API
configuration points to the backend URL being used.

## Tests and evaluation

Run the core unit tests:

``` bash
pytest tests/test_types.py tests/test_spatial_engine.py tests/test_planner.py tests/test_jev_ranker.py -v
```

Run the full suite when practical:

``` bash
pytest -v
```

The exact tests available depend on the current checkout. Live API tests
should be explicitly enabled and treated separately from unit tests.

Use `eval.py` with labelled ground-truth data to measure precision@K. Do
not publish accuracy, precision, latency, or coverage figures unless the
code measured them and the evaluation inputs are documented.

## Spatial semantics and coordinate systems

-   Spatial operations must be deterministic and implemented in
    geospatial code, not inferred by the LLM.
-   Distance-based operations must use a suitable projected coordinate
    reference system with metre units.
-   Verify the CRS from actual imagery and vector metadata. **EPSG:32723
    is an unverified assumption for Rio until confirmed from the source
    data.**
-   Confirm pixel-to-geographic alignment before interpreting
    image-derived locations.
-   Consult `docs/semantics.md` for exact operation and feature-flag
    semantics.
-   Never invent OSM keys, column names, file paths, or measurements.

## Implementation status and limitations

This project includes a mix of implemented code paths, optional
integrations, stubs, and proposed architecture. Verify the current
checkout before claiming a component is operational.

-   **LLM planner:** OpenRouter may be used when configured and
    reachable. The rule-based planner is a fallback and must be labelled
    as such.
-   **Vision retrieval:** SkyCLIP/FAISS requires the model weights,
    index, and tile metadata. A loaded model does not establish
    retrieval accuracy.
-   **Detection/segmentation:** Grounding DINO, SAM 2/SAMGeo, and
    OpenGeoAI are part of the stated technology approach. Do not claim
    they run in a specific query path without checking the
    implementation.
-   **Jev AI:** A local weighted scorer must be labelled **"Local
    ranking."** Show Jev AI as active only after a real successful API
    call.
-   **Translation:** If translation passes text through without a
    successful provider response, label it as a fallback.
-   **Sample data:** All fixture/sample results shown in the UI must be
    labelled **"Sample data."**
-   **Cached results:** Label cached outputs as cached, not as fresh
    inferences.
-   **Data provenance:** Describe imagery and OSM according to actual
    source and preparation records. Never present synthetic/fixture data
    as live OSM or fresh model output.
-   **Resolution limits:** Small features such as solar panels and
    narrow drains may not be reliably visible at the available
    resolution. If not found, say "not found"; do not invent detections.
-   **Unverified assumptions:** Record them in `docs/design.md`, section
    8.

### Proposed feature flags

These flags are proposed and should remain off by default unless their
implementation and tests are verified.

  ------------------------------------------------------------------------------
  Flag                    Default                 Purpose
  ----------------------- ----------------------- ------------------------------
  `FEATURE_NEGATE`        `false`                 Enables `relations[].negate`

  `FEATURE_MIN_AREA`      `false`                 Enables
                                                  `target.filters.min_area_m2`

  `DEMO_MODE`             `false`                 Serves demo/fixture data with
                                                  a visible "Sample data" label
  ------------------------------------------------------------------------------

When a proposed flag is off, its associated behavior must remain inert.

## Attribution

-   **SpaceNet Buildings v1** --- [CC BY-SA
    4.0](https://creativecommons.org/licenses/by-sa/4.0/); Van Etten et
    al., [arXiv:1807.01232](https://arxiv.org/abs/1807.01232).
-   **OpenStreetMap** --- © OpenStreetMap contributors; data is
    available under the [Open Database License
    (ODbL)](https://opendatacommons.org/licenses/odbl/).
-   **SkyScript** --- Wang et al.,
    [arXiv:2312.12856](https://arxiv.org/abs/2312.12856); check upstream
    terms for applicable model and dataset use.
-   **Map tiles** --- if using the configured CARTO basemap, attribute ©
    CARTO and © OpenStreetMap contributors as required by the service.

Keep the attribution page accessible from the main UI.

## Demo release checklist

-   [ ] Requirements REQ-001 through REQ-016 checked against the
    specification.
-   [ ] Fixture results labelled **"Sample data."**
-   [ ] Cached outputs labelled as cached.
-   [ ] Local ranking not described as Jev AI.
-   [ ] Translation fallback identified as a fallback.
-   [ ] Attribution page reachable from the main UI.
-   [ ] `/export` returns a valid GeoJSON `FeatureCollection` consistent
    with displayed results.
-   [ ] Distance operations use a verified projected CRS with metre
    units.
-   [ ] Proposed `negate` and `min_area_m2` fields remain inert while
    flags are disabled.
-   [ ] `eval.py` measures precision@K using labelled ground truth.
-   [ ] `data/provenance.json` exists and contains required keys for the
    data actually processed.
-   [ ] No API keys, local secrets, large model weights, or private
    datasets are committed.
-   [ ] README claims match the actual repository state.

## Project documents

-   `docs/GEOAI05_SPEC_v2.md` --- requirements and project source of
    truth.
-   `docs/design.md` --- architecture and documented assumptions.
-   `docs/semantics.md` --- plan and spatial-operation semantics.
-   `docs/phase_gate_report_template.md` --- phase-gate reporting
    template.
