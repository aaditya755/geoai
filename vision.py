"""
vision.py — concept grounding for GeoLens AI.

Dispatches to the correct grounding path based on concept kind:
  instance  → SkyCLIP FAISS retrieval (multi-crop mean-pool)
  osm_only  → direct OSM GeoDataFrame lookup (no model inference)

Returns a GeoDataFrame with columns:
  tile_id, bbox, score, concept_id, geometry, measured_distance_m (NaN before spatial step)

Unsupported / invisible concepts return an empty DataFrame with
a not_found_message set — the caller should surface this honestly.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

# ---------------------------------------------------------------------------
# Detection cache (SHOULD — REQ-022)
# Keyed by (query_hash, tile_id). Stored in data/cache/detections/.
# ---------------------------------------------------------------------------
DETECTION_CACHE_DIR = Path("data/cache/detections")
FEATURE_CACHE = os.environ.get("FEATURE_DETECTION_CACHE", "false").lower() == "true"

RIO_CRS = "EPSG:32723"
WGS84 = "EPSG:4326"

# Top-K tiles to retrieve from FAISS
DEFAULT_TOP_K = 50


def _query_hash(concept: str, kind: str) -> str:
    return hashlib.sha1(f"{concept}|{kind}".encode()).hexdigest()[:12]


def _cache_path(concept: str, kind: str) -> Path:
    return DETECTION_CACHE_DIR / f"{_query_hash(concept, kind)}.parquet"


def _load_cache(concept: str, kind: str) -> Optional[gpd.GeoDataFrame]:
    if not FEATURE_CACHE:
        return None
    p = _cache_path(concept, kind)
    if p.exists():
        return gpd.read_parquet(p)
    return None


def _save_cache(gdf: gpd.GeoDataFrame, concept: str, kind: str) -> None:
    if not FEATURE_CACHE:
        return
    DETECTION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = _cache_path(concept, kind)
    gdf.to_parquet(p)


# ---------------------------------------------------------------------------
# OSM-only grounding
# ---------------------------------------------------------------------------

def _ground_osm_only(
    concept: str,
    osm_layers: dict,
    concepts_registry: dict,
) -> Tuple[gpd.GeoDataFrame, Optional[str]]:
    """
    Look up concept directly in the OSM vector layers.
    No vision model is called.

    Returns (GeoDataFrame, not_found_message).
    not_found_message is None on success.
    """
    concept_def = concepts_registry.get(concept)
    if concept_def is None:
        return gpd.GeoDataFrame(), f"Concept '{concept}' not found in concepts registry."

    not_visible = concept_def.get("not_visible_note")
    osm_key = concept_def.get("osm_key")
    osm_value = concept_def.get("osm_value", "*")

    layer = osm_layers.get(concept)
    if layer is None:
        layer = osm_layers.get(osm_key)
    if layer is None or layer.empty:
        msg = (
            f"No OSM data found for concept '{concept}' "
            f"(osm_key={osm_key!r}, osm_value={osm_value!r}). "
            "Make sure data_prep.py has been run."
        )
        if not_visible:
            msg = f"[too small to see at this resolution] {not_visible.strip()} OSM fallback also returned no data."
        return gpd.GeoDataFrame(), msg

    result = layer.copy()
    result["tile_id"] = ""       # OSM features don't have tile_ids
    result["bbox"] = result.geometry.apply(
        lambda g: list(g.bounds) if g is not None else [0, 0, 0, 0]
    )
    result["score"] = 1.0        # OSM data is deterministic; score=1
    result["concept_id"] = concept
    result["measured_distance_m"] = float("nan")
    result["rank"] = 0

    msg = None
    if not_visible:
        msg = f"[visibility note] {not_visible.strip()} OSM data returned."

    return result, msg


# ---------------------------------------------------------------------------
# Instance grounding (SkyCLIP)
# ---------------------------------------------------------------------------

def _ground_instance(
    concept: str,
    concepts_registry: dict,
    index_path: Path,
    meta_path: Path,
    tile_footprints: gpd.GeoDataFrame,
    top_k: int = DEFAULT_TOP_K,
) -> Tuple[gpd.GeoDataFrame, Optional[str]]:
    """
    Retrieve top-K tiles from FAISS using SkyCLIP text embedding,
    then perform object detection on retrieved tiles.

    Returns (GeoDataFrame, not_found_message).
    """
    try:
        import faiss
    except ImportError:
        return gpd.GeoDataFrame(), (
            "faiss not installed. Run: pip install faiss-cpu  "
            "(or faiss-gpu on a GPU machine). "
            "The FAISS index is also required — run index_tiles.py first (tasks.md P3.3 [MANUAL])."
        )

    from skyclip_loader import embed_text, get_device, load_skyclip
    from object_detector import detect_objects_in_tiles

    concept_def = concepts_registry.get(concept)
    if concept_def is None:
        return gpd.GeoDataFrame(), f"Concept '{concept}' not in concepts.yaml registry."

    not_visible = concept_def.get("not_visible_note")
    skyclip_text = concept_def.get("skyclip_text", concept)

    if not index_path.exists():
        return gpd.GeoDataFrame(), (
            "SkyCLIP FAISS index not found. "
            "Run index_tiles.py on a GPU machine first (tasks.md P3.3 [MANUAL])."
        )

    if not meta_path.exists():
        return gpd.GeoDataFrame(), "skyclip_meta.json not found. Re-run index_tiles.py."

    # Load FAISS index + metadata
    index = faiss.read_index(str(index_path))
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    tile_ids = [t["tile_id"] for t in meta["tiles"]]

    # Embed the text query
    model, preprocess, tokenizer = load_skyclip()
    device = get_device()
    query_vec = embed_text(model, tokenizer, skyclip_text, device=device)
    query_vec = query_vec.astype("float32").reshape(1, -1)

    # FAISS search to get top-K tiles
    k = min(top_k, index.ntotal)
    scores, indices = index.search(query_vec, k)

    scores = scores[0]
    indices = indices[0]

    # Get tile IDs for object detection
    retrieved_tile_ids = []
    for score, idx in zip(scores, indices):
        if idx >= 0 and score > 0.1:  # Filter very low similarity scores
            tile_id = tile_ids[idx]
            retrieved_tile_ids.append(tile_id)
    
    if not retrieved_tile_ids:
        msg = (
            f"No relevant tiles found for concept '{concept}' "
            f"(skyclip_text={skyclip_text!r}). "
        )
        if not_visible:
            msg = f"[too small to see at this resolution] {not_visible.strip()}"
        return gpd.GeoDataFrame(), msg

    # Perform object detection on retrieved tiles
    print(f"[vision] Running object detection on {len(retrieved_tile_ids)} tiles for '{concept}'")
    detected_objects = detect_objects_in_tiles(retrieved_tile_ids, concept)
    
    if detected_objects.empty:
        msg = f"No {concept} objects detected in {len(retrieved_tile_ids)} retrieved tiles."
        if not_visible:
            msg = f"[visibility note] {not_visible.strip()} No objects detected in retrieved tiles."
        return gpd.GeoDataFrame(), msg

    # Ensure output has correct CRS and columns
    if detected_objects.crs != RIO_CRS:
        detected_objects = detected_objects.to_crs(RIO_CRS)
    
    # Add required columns if missing
    required_cols = ['tile_id', 'bbox', 'score', 'concept_id', 'measured_distance_m', 'rank']
    for col in required_cols:
        if col not in detected_objects.columns:
            if col == 'measured_distance_m':
                detected_objects[col] = float('nan')
            elif col == 'rank':
                detected_objects[col] = 0
            else:
                detected_objects[col] = ""

    not_found_msg = None
    if not_visible:
        not_found_msg = f"[visibility note] {not_visible.strip()} Results may be unreliable."

    print(f"[vision] Detected {len(detected_objects)} {concept} objects")
    return detected_objects, not_found_msg


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ground(
    target,                        # types.Target
    osm_layers: dict,
    concepts_registry: dict,
    index_path: Path = Path("data/embeddings/skyclip.index"),
    meta_path: Path = Path("data/embeddings/skyclip_meta.json"),
    tile_footprints: Optional[gpd.GeoDataFrame] = None,
    top_k: int = DEFAULT_TOP_K,
) -> Tuple[gpd.GeoDataFrame, Optional[str]]:
    """
    Ground a plan target to a GeoDataFrame of candidates.

    Parameters
    ----------
    target            : types.Target from the validated plan
    osm_layers        : dict of concept_name → GeoDataFrame (loaded OSM data)
    concepts_registry : dict loaded from concepts.yaml
    index_path        : path to FAISS index (instance kind only)
    meta_path         : path to skyclip_meta.json (instance kind only)
    tile_footprints   : GeoDataFrame of tile footprints with tile_id column
    top_k             : number of candidates to retrieve

    Returns
    -------
    (GeoDataFrame of candidates, not_found_message or None)
    """
    concept = target.concept
    kind = target.kind.value

    # Check cache first
    cached = _load_cache(concept, kind)
    if cached is not None:
        return cached, None

    if kind == "osm_only":
        result, msg = _ground_osm_only(concept, osm_layers, concepts_registry)
    elif kind == "instance":
        if tile_footprints is None:
            tile_footprints = gpd.GeoDataFrame()
        result, msg = _ground_instance(
            concept, concepts_registry, index_path, meta_path,
            tile_footprints, top_k
        )
    else:
        return gpd.GeoDataFrame(), f"Unknown concept kind: {kind!r}"

    # Save to cache if successful and non-empty
    if not result.empty and msg is None:
        _save_cache(result, concept, kind)

    return result, msg
