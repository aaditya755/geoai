"""
app.py — FastAPI backend for GeoLens AI.

POST /chat  — natural language → plan → vision → spatial → ranking → JSON response
GET  /health — health check
GET  /attribution — dataset attributions

Feature flags (env vars):
  DEMO_MODE=true     — serve from data/fixtures/demo_results.json (offline demo)
  MISTRAL_API_KEY    — enable real Mistral calls
  SARVAM_API_KEY     — enable Sarvam AI translation
  JEV_API_KEY        — enable Jev AI ranking API
  FEATURE_NEGATE     — enable negate spatial op (PROPOSED)
  FEATURE_MIN_AREA   — enable min_area_m2 filter (PROPOSED)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import geopandas as gpd
import yaml
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import jev_ranker
import planner_agent
import spatial_engine
import vision
from translate import detect_language, translate
from geolens_types import ChatResponse
from llm_provider import get_provider_info

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEMO_MODE: bool = os.environ.get("DEMO_MODE", "false").lower() == "true"
DEMO_FIXTURE = Path("data/fixtures/demo_results.json")
CONCEPTS_YAML = Path("concepts.yaml")
TILE_INDEX_PATH = Path("data/processed/tile_index.geojson")
OSM_ROADS_PATH = Path("data/raw/osm/roads.parquet")
OSM_BUILDINGS_PATH = Path("data/raw/osm/buildings.parquet")

RIO_CRS = "EPSG:32723"

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GeoLens AI",
    description="Natural-language search over aerial tiles + OpenStreetMap vectors (Rio de Janeiro).",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup: load concepts registry + OSM layers
# ---------------------------------------------------------------------------

_concepts_registry: Dict[str, Any] = {}
_osm_layers: Dict[str, gpd.GeoDataFrame] = {}
_tile_footprints: Optional[gpd.GeoDataFrame] = None


@app.on_event("startup")
async def _startup() -> None:
    global _concepts_registry, _osm_layers, _tile_footprints

    # Load concepts.yaml
    if CONCEPTS_YAML.exists():
        with open(CONCEPTS_YAML, "r", encoding="utf-8") as f:
            _concepts_registry = yaml.safe_load(f) or {}
        print(f"[app] Loaded {len(_concepts_registry)} concepts from {CONCEPTS_YAML}")
    else:
        print(f"[app] WARNING: {CONCEPTS_YAML} not found — vision grounding will be limited")

    # Load OSM layers
    for name, path in [("road", OSM_ROADS_PATH), ("building", OSM_BUILDINGS_PATH)]:
        if path.exists():
            try:
                gdf = gpd.read_parquet(path)

                # When the file mixes buildings and parks, split them cleanly.
                if name == "building":
                    # Extract parks first (leisure=park rows have building=NaN).
                    if "leisure" in gdf.columns:
                        park_features = gdf[gdf["leisure"] == "park"].copy()
                        if not park_features.empty:
                            _osm_layers["park"] = park_features
                            print(f"[app] Extracted OSM layer 'park': {len(park_features)} features")
                    
                    # Filter to actual buildings only (non-null building tag).
                    if "building" in gdf.columns:
                        building_features = gdf[gdf["building"].notna()].copy()
                        _osm_layers[name] = building_features
                        print(f"[app] Loaded OSM layer '{name}': {len(building_features)} features")
                    else:
                        _osm_layers[name] = gdf
                        print(f"[app] Loaded OSM layer '{name}': {len(gdf)} features")
                else:
                    _osm_layers[name] = gdf
                    print(f"[app] Loaded OSM layer '{name}': {len(gdf)} features")
                        
            except Exception as e:
                print(f"[app] WARNING: failed to load OSM layer '{name}' from {path}: {e}")
        else:
            print(f"[app] WARNING: OSM layer '{name}' not found at {path} — run data_prep.py first")

    # Load tile footprints
    if TILE_INDEX_PATH.exists():
        try:
            _tile_footprints = gpd.read_file(TILE_INDEX_PATH)
            print(f"[app] Loaded tile index: {len(_tile_footprints)} tiles")
        except Exception as e:
            print(f"[app] WARNING: failed to load tile index: {e}")
    else:
        print(f"[app] WARNING: tile index not found at {TILE_INDEX_PATH} — run data_prep.py first")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    lang: Optional[str] = None   # BCP-47 language code; None = assume English


class ChatResponseModel(BaseModel):
    session_id: str
    plan: Dict[str, Any]
    candidates: list
    results: list
    session_history: list
    error: Optional[str] = None
    not_found_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_demo_fixture(query: str = "") -> Dict[str, Any]:
    """Load appropriate demo fixture based on query content."""
    
    # Determine which fixture to use based on query keywords
    query_lower = query.lower()
    
    if any(word in query_lower for word in ['airport', 'runway', 'terminal', 'aviation', 'flight']):
        fixture_path = Path("data/fixtures/demo_airports.json")
    elif any(word in query_lower for word in ['sea', 'ocean', 'coast', 'water', 'beach', 'marine']):
        # If query mentions water/sea but not airports, still use airports near sea
        if 'airport' not in query_lower:
            fixture_path = Path("data/fixtures/demo_airports.json")
        else:
            fixture_path = Path("data/fixtures/demo_airports.json")
    else:
        # Default to swimming pools
        fixture_path = DEMO_FIXTURE
    
    if not fixture_path.exists():
        # Fallback to default fixture
        fixture_path = DEMO_FIXTURE
        
    if not fixture_path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "DEMO_MODE is enabled but demo fixture not found at data/fixtures/demo_results.json. "
                "Run the pipeline once on real data and save the result there (task P7.5)."
            ),
        )
        
    with open(fixture_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Mark all data as sample data when serving from fixture
    data["_sample_data"] = True
    return data


def _build_osm_layers_for_plan(plan) -> Dict[str, gpd.GeoDataFrame]:
    """Return only the OSM layers referenced by this plan's relations."""
    needed = {rel.reference_concept for rel in plan.relations}
    layers = {}
    for concept in needed:
        if concept in _osm_layers:
            layers[concept] = _osm_layers[concept]
        else:
            # Try to find a matching concept in the registry
            for layer_name, gdf in _osm_layers.items():
                if layer_name in concept or concept in layer_name:
                    layers[concept] = gdf
                    break
    return layers


# ---------------------------------------------------------------------------
# /chat endpoint
# ---------------------------------------------------------------------------

@app.post("/chat", response_model=ChatResponseModel)
async def chat(req: ChatRequest) -> ChatResponseModel:
    """
    Main pipeline endpoint:
      1. Translate query to English (if needed)
      2. Plan (Mistral or fallback)
      3. Ground (vision or OSM)
      4. Spatial filter
      5. Rank (Jev AI or local)
      6. Return JSON
    """

    # --- Demo mode shortcut ---
    if DEMO_MODE:
        fixture = _load_demo_fixture(req.query)
        return ChatResponseModel(**fixture)

    # --- Step 1: Translate to English ---
    query_en = req.query
    if req.lang and req.lang not in ("en", "en-IN", "en-US", "en-GB"):
        query_en = translate(req.query, from_lang=req.lang, to_lang="en-IN")

    # --- Step 2: Plan ---
    try:
        plan, session_id = planner_agent.plan(query_en, session_id=req.session_id)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Planning failed: {e}")

    # --- Step 3: Ground ---
    candidates_gdf, not_found_msg = vision.ground(
        target=plan.target,
        osm_layers=_osm_layers,
        concepts_registry=_concepts_registry,
        tile_footprints=_tile_footprints,
    )

    if candidates_gdf.empty:
        history = planner_agent.get_session_history(session_id)
        return ChatResponseModel(
            session_id=session_id,
            plan=plan.to_dict(),
            candidates=[],
            results=[],
            session_history=history,
            not_found_message=not_found_msg or f"No candidates found for '{plan.target.concept}'.",
        )

    # --- Step 4: Spatial filter ---
    if plan.relations:
        osm_for_plan = _build_osm_layers_for_plan(plan)
        try:
            filtered_gdf = spatial_engine.apply_relations(
                candidates=candidates_gdf,
                relations=plan.relations,
                osm_layers=osm_for_plan,
            )
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Spatial filtering failed: {e}")
    else:
        filtered_gdf = candidates_gdf.copy()
        if "measured_distance_m" not in filtered_gdf.columns:
            filtered_gdf["measured_distance_m"] = float("nan")

    # --- Step 5: Rank ---
    try:
        ranked_df = jev_ranker.rank(filtered_gdf)
    except Exception as e:
        # Ranking is advisory; don't fail the whole request
        ranked_df = filtered_gdf.copy()
        ranked_df["rank"] = range(1, len(ranked_df) + 1)
        ranked_df["jev_score"] = ranked_df.get("score", 0.0)

    # --- Apply limit ---
    if plan.limit:
        ranked_df = ranked_df.head(plan.limit)

    # --- Serialise ---
    def _row_to_dict(row) -> Dict[str, Any]:
        d = {
            "tile_id": str(row.get("tile_id", "")),
            "bbox": row.get("bbox", []),
            "score": float(row.get("score", 0.0)),
            "concept_id": str(row.get("concept_id", "")),
            "measured_distance_m": float(row.get("measured_distance_m", float("nan"))),
            "rank": int(row.get("rank", 0)),
            "jev_score": float(row.get("jev_score", 0.0)),
            "score_breakdown": row.get("score_breakdown", {}),
        }
        # Add geometry as WKT for frontend (GeoJSON export handled by /export)
        if hasattr(row, "geometry") and row.geometry is not None:
            d["geometry_wkt"] = row.geometry.wkt
        return d

    candidates_list = [_row_to_dict(row) for _, row in candidates_gdf.iterrows()]
    results_list = [_row_to_dict(row) for _, row in ranked_df.iterrows()]
    history = planner_agent.get_session_history(session_id)

    return ChatResponseModel(
        session_id=session_id,
        plan=plan.to_dict(),
        candidates=candidates_list,
        results=results_list,
        session_history=history,
        not_found_message=not_found_msg,
    )


# ---------------------------------------------------------------------------
# /export endpoint
# ---------------------------------------------------------------------------

class ExportRequest(BaseModel):
    results: list   # list of result dicts from /chat response


@app.post("/export")
async def export_geojson(req: ExportRequest):
    """
    Convert results to a GeoJSON FeatureCollection for download.
    REQ-014.
    """
    from shapely import wkt as shapely_wkt

    features = []
    for r in req.results:
        geom = None
        if r.get("geometry_wkt"):
            try:
                geom_obj = shapely_wkt.loads(r["geometry_wkt"])
                geom = geom_obj.__geo_interface__
            except Exception:
                pass

        if geom is None and r.get("bbox"):
            b = r["bbox"]
            try:
                from shapely.geometry import box
                geom = box(b[0], b[1], b[2], b[3]).__geo_interface__
            except Exception:
                pass

        props = {k: v for k, v in r.items() if k not in ("geometry_wkt",)}
        # Replace NaN with null for valid JSON
        for k, v in props.items():
            try:
                import math
                if isinstance(v, float) and math.isnan(v):
                    props[k] = None
            except Exception:
                pass

        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": props,
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# ---------------------------------------------------------------------------
# /health and /attribution
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "demo_mode": DEMO_MODE,
        "osm_layers_loaded": list(_osm_layers.keys()),
        "tile_footprints_loaded": _tile_footprints is not None and len(_tile_footprints) > 0,
        "planner": get_provider_info(),
    }


@app.get("/attribution")
async def attribution():
    """REQ-016: dataset attributions."""
    return {
        "datasets": [
            {
                "name": "SpaceNet Buildings v1 (Rio de Janeiro)",
                "licence": "CC BY-SA 4.0",
                "citation": "arXiv:1807.01232",
                "url": "https://spacenet.ai/spacenet-buildings-dataset-v1/",
            },
            {
                "name": "OpenStreetMap",
                "licence": "ODbL",
                "attribution": "© OpenStreetMap contributors",
                "url": "https://www.openstreetmap.org/copyright",
            },
            {
                "name": "SkyScript",
                "licence": "See arXiv",
                "citation": "arXiv:2312.12856",
                "url": "https://arxiv.org/abs/2312.12856",
            },
        ]
    }


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

