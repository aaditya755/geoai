# GeoLens AI (GEOAI 05) — Design

Spec: geolens-demo  
Source of truth: docs/GEOAI05_SPEC_v2.md  

---

## 1. Architecture Overview (per spec section 5)

```
User Query (natural language)
   │
   ▼
planner_agent.py  ──── Mistral API (or fallback) ────► plan.json (schema-validated)
   │
   ▼
vision.py  ──── FAISS index (SkyCLIP embeddings) ────► candidates DataFrame
   │
   ▼
spatial_engine.py  ──── OSM GeoDataFrame (EPSG:32723) ────► filtered results + measured_distance_m
   │
   ▼
jev_ranker.py  ──── deterministic scorer (+ optional JevClient stub) ────► ranked shortlist
   │
   ▼
app.py  ──── FastAPI /chat endpoint ────► JSON response
   │
   ▼
frontend/ (Vite + React) ──── map + results + export
```

**Principle:** The LLM (Mistral) writes ONLY a schema-validated JSON plan. No geometric decisions are made by the LLM. Vision models find candidates. Deterministic GeoPandas code applies spatial rules.

---

## 2. Data Layout (per spec section 6.3)

```
data/
  raw/
    spacenet_rio/          # SpaceNet Buildings v1 tiles [MANUAL download]
    osm/                   # OSM PBF or Overpass extracts
  processed/
    tiles_8bit/            # 8-bit brightness-stretched tiles
    tile_index.geojson     # tile footprints with tile_id
    buildings.parquet      # building polygons (EPSG:32723)
    roads.parquet          # road centrelines (EPSG:32723)
  embeddings/
    skyclip.index          # FAISS flat-IP index
    skyclip_meta.json      # tile_id → crop offsets mapping
  cache/
    detections/            # keyed by query_hash_tileid.parquet
  fixtures/
    demo_results.json      # cached real results for Demo mode
  annotations/
    labelled_crops.json    # [MANUAL] ~100 hand-labelled crops for eval
  provenance.json          # data prep metadata
```

All `data/` contents are git-ignored.

---

## 3. API Contracts (per spec sections 6.1–6.6)

### POST /chat

**Request:**
```json
{ "query": "string", "session_id": "string|null", "lang": "string|null" }
```

**Response:**
```json
{
  "session_id": "string",
  "plan": { },
  "candidates": [
    { "tile_id": "str", "bbox": [0.0, 0.0, 0.0, 0.0], "score": 0.0, "concept_id": "str" }
  ],
  "results": [
    { "tile_id": "str", "bbox": [0.0, 0.0, 0.0, 0.0], "score": 0.0, "measured_distance_m": 0.0, "rank": 1 }
  ],
  "session_history": [
    { "query": "str", "plan": {} }
  ]
}
```

### Plan Schema

```json
{
  "target": {
    "concept": "string",
    "kind": "instance|osm_only",
    "filters": {
      "min_area_m2": null
    }
  },
  "relations": [
    {
      "type": "dwithin|intersects|negate",
      "reference_concept": "string",
      "distance_m": null,
      "negate": false
    }
  ],
  "limit": null,
  "session_id": null
}
```

**PROPOSED fields (feature-flagged):** `relations[].negate` and `target.filters.min_area_m2`. Both default to null/false. No other code shall depend on them until the team agrees. See Feature Flags section.

### Detection Output Columns (per spec section 6.5)

| Column | Type | Description |
|--------|------|-------------|
| tile_id | str | SpaceNet tile identifier |
| bbox | list[float] | [x1, y1, x2, y2] in pixel coords |
| score | float | SkyCLIP cosine similarity |
| concept_id | str | concept name from plan |
| measured_distance_m | float | distance to reference (NaN before spatial step) |
| rank | int | Jev AI rank (0 before ranking step) |

---

## 4. Vision Grounding by Concept Kind (per spec section 7.3)

| Kind | Path | Notes |
|------|------|-------|
| instance | SkyCLIP FAISS retrieval → multi-crop → mean pool | Returns top-K by cosine similarity |
| osm_only | Direct OSM GeoDataFrame lookup | No vision model called |
| roof_attr (SHOULD) | RGB crop → lightweight classifier | Returns label + confidence |
| road_attr (SHOULD) | OSM highway tag lookup | Returns tag value or "unknown" |

**Unsupported / invisible concepts** (solar panels, narrow drains at 0.5 m/px resolution): return a structured `"not found / too small to see at this resolution"` message. OSM fallback is attempted where the concept has an OSM key.

---

## 5. Spatial Engine Operations (per spec section 7.4)

All distances computed in **EPSG:32723** (UTM zone 23S, Rio de Janeiro).

- **dwithin(candidates, reference, distance_m):** Returns rows where geometry is within `distance_m` metres of reference; adds `measured_distance_m` column.
- **intersects(candidates, reference):** Returns rows where geometries intersect.
- **negate(inner_result, all_candidates):** Returns `all_candidates NOT IN inner_result`. **[PROPOSED, feature-flagged FEATURE_NEGATE]** — no production code depends on this until the team agrees.

---

## 6. Sequence Diagrams

### 6.1 First Query

```
User ──► app.py POST /chat
  app.py ──► translate.py.translate(query, detected_lang, "en")   [if non-English]
  app.py ──► planner_agent.py.plan(query_en)
    planner_agent.py ──► Mistral API  [or fallback rule-based planner]
    ◄── plan.json (schema-validated)
  app.py ──► vision.py.ground(plan.target)
    vision.py ──► FAISS index (SkyCLIP)   [if kind == "instance"]
    vision.py ──► OSM GeoDataFrame         [if kind == "osm_only"]
    ◄── candidates DataFrame
  app.py ──► spatial_engine.py.apply(candidates, plan.relations)
    spatial_engine.py ──► OSM GeoDataFrame (EPSG:32723)
    ◄── filtered results + measured_distance_m
  app.py ──► jev_ranker.py.rank(results)
    jev_ranker.py ──► local scorer  [or JevClient if key set]
    ◄── ranked shortlist
  ◄── JSON response {session_id, plan, candidates, results, session_history}
User ◄── map + results + export
```

### 6.2 Follow-up Query ("now within 50 m")

```
User ──► app.py POST /chat  { query: "now within 50 m", session_id: "<id>" }
  app.py ──► session store: load previous plan by session_id
  app.py ──► planner_agent.py.amend(previous_plan, delta_query)
    planner_agent.py ──► Mistral API: "edit only changed fields in this plan: ..."
    ◄── amended plan.json (schema-validated)
  app.py ──► vision.py.ground(plan.target)   [cache lookup first]
    ◄── candidates DataFrame (cached or fresh)
  app.py ──► spatial_engine.py.apply(candidates, amended_plan.relations)
    ◄── filtered results + measured_distance_m
  app.py ──► jev_ranker.py.rank(results)
    ◄── ranked shortlist
  ◄── JSON response (full plan shown as chips; changed chip highlighted)
```

### 6.3 Failure Fallbacks

```
Mistral API fails      ──► local rule-based planner (plan_fallback.py)
FAISS index missing    ──► error: "Run index_tiles.py first"  [no fake results]
OSM data missing       ──► error: "Run data_prep.py first"    [no fake results]
Concept not visible    ──► "not found / too small to see at this resolution" + OSM fallback attempt
JevClient unavailable  ──► local deterministic scorer (always available)
Sarvam API unavailable ──► passthrough (query used as-is in English)
```

---

## 7. Adapters

### 7.1 LLM provider — llm_provider.py

**Interface:** `LLMPlannerProvider.generate_plan(messages, response_schema)`

```python
class LLMPlannerProvider(ABC):
    def generate_plan(self, messages: list, response_schema: dict | None) -> str: ...
    def provider_name(self) -> str: ...
```

**Current implementation:** `OpenRouterPlannerProvider`
- Endpoint: `POST https://openrouter.ai/api/v1/chat/completions` (OpenAI-compatible)
- Structured output: `response_format.type = "json_schema"`, `strict = true`
- Provider routing: `require_parameters: true` to prevent silent fallback to endpoints that ignore `response_format`
- Retries: bounded (default 2) on 429/5xx; no retry on 400/401/403/422
- Timeout: configurable via `OPENROUTER_TIMEOUT_S` (default 30 s)
- Local `validate_plan()` runs on every response regardless of structured output mode
- Falls back to prompt-only JSON extraction if endpoint rejects `response_format`

**Switching providers:** Implement `LLMPlannerProvider`, call `get_provider()` in `llm_provider.py`. `planner_agent.py` requires no changes.

**Selected model:** `google/gemini-2.0-flash-001`
- Confirmed structured output (`json_schema`) support via OpenRouter/Google endpoint
- Good spatial/relational reasoning; strong JSON schema adherence
- Low cost (~$0.10/$0.40 per 1M input/output tokens)
- Stable versioned endpoint

**Free alternative (development only):** `google/gemini-2.0-flash-exp:free`
- Zero cost, rate-limited, structured output confirmed
- Set via `OPENROUTER_MODEL=google/gemini-2.0-flash-exp:free`
- Not recommended for evaluation or production; may be rate-limited

**Configuration:**
| Variable | Default | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Required for live inference |
| `OPENROUTER_MODEL` | `google/gemini-2.0-flash-001` | Model identifier |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base URL override |
| `OPENROUTER_TIMEOUT_S` | `30` | Request timeout |
| `OPENROUTER_MAX_RETRIES` | `2` | Max retries on transient errors |

**Security:** API key is only placed in the `Authorization` header. It is never logged, never included in error messages returned to the client, and never serialised to the plan or session history.

**Interface:**
```python
def score_local(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Deterministic weighted scoring.
    Weights: confidence=0.4, proximity=0.3, size=0.3.
    Adds columns: jev_score (float), score_breakdown (dict).
    Output is advisory: 'ranks for human review'.
    """

class JevClient:
    """Stub interface. Real implementation injected via JEV_API_KEY."""
    def rank(self, results_df: pd.DataFrame) -> pd.DataFrame: ...
```

**Fallback:** Always use `score_local` when `JevClient` is unavailable.

### 7.2 translate.py

**Interface:**
```python
def translate(text: str, from_lang: str, to_lang: str) -> str:
    """
    Translate text from from_lang to to_lang.
    Implementation: Sarvam AI translate endpoint (key from SARVAM_API_KEY).
    # TODO: verify Sarvam AI endpoint URL and request schema — UNVERIFIED at design time.
    Fallback: return text unchanged (passthrough).
    """
```

**Planner invariant:** Planner always receives and returns English. Frontend shows English plan chips regardless of input language.

---

## 8. Unverified Assumptions

> **Single consolidated list.** All items below are unverified at design time. Do not report them as facts.

1. **SpaceNet v1 Rio tile resolution** is approximately 0.5 m/px — used to justify "too small to see" decisions for sub-metre features. Must be confirmed from SpaceNet metadata.
2. **Sarvam AI translate endpoint** — URL and request schema could not be verified at design time. Marked `# TODO: verify Sarvam AI endpoint` in translate.py.
3. **Jev AI ranking API schema** — stub interface only; real key and schema injected later.
4. **FAISS flat-IP index** is sufficient for the SpaceNet Rio subset size (< 10,000 tiles). May need IVF index at larger scale; to be revisited after index build.
5. **EPSG:32723** (UTM zone 23S) is the appropriate projection for Rio de Janeiro — standard for that region, but should be confirmed against SpaceNet tile metadata header.

---

## 9. Feature Flags

| Flag | Default | Controls |
|------|---------|----------|
| FEATURE_NEGATE | False | relations[].negate spatial operation (PROPOSED) |
| FEATURE_MIN_AREA | False | target.filters.min_area_m2 plan field (PROPOSED) |
| DEMO_MODE | False | Serve results from data/fixtures/demo_results.json |

All flags read from environment variables (e.g. `.env`). Default False when absent. **No production code path shall depend on FEATURE_NEGATE or FEATURE_MIN_AREA until the team formally agrees to promote them.**

---

## 10. UI Design

### 10.1 Theme
- Background: #0B1020
- Panels: #121A33
- Accents: teal #2DD4BF, violet #8B5CF6, pink #E0559A
- Font: Inter

### 10.2 Layout
- **Top bar:** dataset chip, language dropdown
- **Left panel:** chat input, animated 4-step pipeline card (Understanding → Searching imagery → Applying spatial rules → Ranking), editable plan chips, collapsible plan JSON
- **Centre:** map with road classes, glowing markers, dashed bounding boxes, buffer ring on selection
- **Right panel tabs:** Results, Ranking (Jev AI), Evidence, Export

### 10.3 Honesty Rules in UI
- Every fixture / cached result is labelled **"Sample data"**.
- "Equivalent SQL" expression labelled **"Equivalent (not executed)"** (REQ-025).
- Unsupported concepts return plain message: "not found / too small to see at this resolution".
- No invented numbers shown; all displayed metrics come from code measurement.
