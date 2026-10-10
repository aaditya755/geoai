"""
spatial_engine.py — deterministic spatial filtering for GeoLens AI.

ALL geometry operations happen here, in Python/GeoPandas.
The LLM never makes geometric decisions; it only produces a Plan.

Projection: EPSG:32723 (UTM Zone 23S) for Rio de Janeiro.
All distances are in metres.

Feature flags:
  FEATURE_NEGATE  — enables the negate() operation (PROPOSED)
"""

from __future__ import annotations

import math
import os
from typing import Optional

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

# PROPOSED negate feature flag — default off
FEATURE_NEGATE: bool = os.environ.get("FEATURE_NEGATE", "false").lower() == "true"

# UTM Zone 23S — appropriate for Rio de Janeiro
RIO_CRS = "EPSG:32723"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_projected(gdf: gpd.GeoDataFrame, crs: str = RIO_CRS) -> gpd.GeoDataFrame:
    """Reproject to a metric CRS if not already there."""
    if gdf.crs is None:
        raise ValueError("GeoDataFrame has no CRS set — cannot project.")
    if gdf.crs.to_epsg() != int(crs.split(":")[1]):
        return gdf.to_crs(crs)
    return gdf


def _candidates_to_gdf(candidates: pd.DataFrame, geom_col: str = "geometry") -> gpd.GeoDataFrame:
    """
    Coerce a plain DataFrame of candidates to a GeoDataFrame.
    Candidates must already have a geometry column (Shapely objects).
    """
    if isinstance(candidates, gpd.GeoDataFrame):
        return candidates
    if geom_col not in candidates.columns:
        raise ValueError(
            f"candidates DataFrame missing '{geom_col}' column. "
            "Run vision.py first to attach geometries."
        )
    return gpd.GeoDataFrame(candidates, geometry=geom_col, crs=RIO_CRS)


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def dwithin(
    candidates: gpd.GeoDataFrame,
    reference: gpd.GeoDataFrame,
    distance_m: float,
) -> gpd.GeoDataFrame:
    """
    Return candidates whose geometry is within distance_m metres of ANY
    geometry in the reference GeoDataFrame.

    Adds/updates the measured_distance_m column with the actual minimum
    distance to the reference set, measured in EPSG:32723.

    Parameters
    ----------
    candidates : GeoDataFrame  — the things to filter (e.g. swimming pools)
    reference  : GeoDataFrame  — the reference layer (e.g. roads)
    distance_m : float         — threshold distance in metres

    Returns
    -------
    GeoDataFrame with only the matching candidates; measured_distance_m column
    contains the actual distance to the nearest reference geometry.
    """
    if candidates.empty:
        return candidates.copy()

    candidates = _ensure_projected(candidates)
    reference = _ensure_projected(reference)

    # Union of reference geometries for distance computation
    ref_union = reference.geometry.union_all()

    distances = candidates.geometry.apply(
        lambda geom: geom.distance(ref_union) if geom is not None and not geom.is_empty else math.nan
    )

    mask = distances <= distance_m
    result = candidates[mask].copy()
    result["measured_distance_m"] = distances[mask]
    return result


def intersects(
    candidates: gpd.GeoDataFrame,
    reference: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Return candidates whose geometry intersects ANY geometry in the reference
    GeoDataFrame.

    Sets measured_distance_m to 0.0 for all matches (they touch or overlap).

    Parameters
    ----------
    candidates : GeoDataFrame
    reference  : GeoDataFrame

    Returns
    -------
    GeoDataFrame with only matching candidates.
    """
    if candidates.empty:
        return candidates.copy()

    candidates = _ensure_projected(candidates)
    reference = _ensure_projected(reference)

    ref_union = reference.geometry.union_all()

    mask = candidates.geometry.apply(
        lambda geom: geom is not None and geom.intersects(ref_union) and not geom.is_empty
    )

    result = candidates[mask].copy()
    result["measured_distance_m"] = 0.0
    return result


def negate(
    inner_result: gpd.GeoDataFrame,
    all_candidates: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    PROPOSED — only active when FEATURE_NEGATE=true.
    Return all_candidates that are NOT in inner_result (by tile_id + bbox).

    The team must agree before any other code depends on this operation.

    Parameters
    ----------
    inner_result   : candidates that matched the inner relation
    all_candidates : the full candidate set

    Returns
    -------
    GeoDataFrame of candidates not present in inner_result.

    Raises
    ------
    RuntimeError if FEATURE_NEGATE is False.
    """
    if not FEATURE_NEGATE:
        raise RuntimeError(
            "negate() is a PROPOSED feature. Set FEATURE_NEGATE=true to enable it. "
            "The team must agree before this is used in production."
        )

    if all_candidates.empty:
        return all_candidates.copy()

    # Use tile_id + bbox string as a compound key
    def _key(row) -> str:
        return f"{row['tile_id']}|{row['bbox']}"

    inner_keys = set(inner_result.apply(_key, axis=1))
    mask = all_candidates.apply(lambda r: _key(r) not in inner_keys, axis=1)
    result = all_candidates[mask].copy()
    # Distance is undefined for negate; leave as NaN
    result["measured_distance_m"] = float("nan")
    return result


# ---------------------------------------------------------------------------
# High-level dispatcher (called from app.py)
# ---------------------------------------------------------------------------

def apply_relations(
    candidates: gpd.GeoDataFrame,
    relations: list,
    osm_layers: dict,
) -> gpd.GeoDataFrame:
    """
    Apply a list of Plan relations to the candidates GeoDataFrame.

    Parameters
    ----------
    candidates : GeoDataFrame  — vision output (instance) or OSM lookup
    relations  : list of Relation dataclass instances (from types.py)
    osm_layers : dict mapping concept_name → GeoDataFrame (road, park, etc.)

    Returns
    -------
    GeoDataFrame with measured_distance_m column; rows filtered by all relations.
    """
    from geolens_types import RelationType  # avoid circular at module level

    result = candidates.copy()
    if "measured_distance_m" not in result.columns:
        result["measured_distance_m"] = float("nan")

    for rel in relations:
        ref_layer = osm_layers.get(rel.reference_concept)
        if ref_layer is None or ref_layer.empty:
            # Fail clearly — do not silently return all candidates
            raise ValueError(
                f"Reference layer '{rel.reference_concept}' not found in osm_layers. "
                "Make sure data_prep.py has been run and the concept name matches concepts.yaml."
            )

        if rel.type.value == "dwithin":
            if rel.distance_m is None:
                raise ValueError(
                    f"Relation type 'dwithin' requires distance_m but got None "
                    f"(reference_concept='{rel.reference_concept}')."
                )
            result = dwithin(result, ref_layer, rel.distance_m)

        elif rel.type.value == "intersects":
            result = intersects(result, ref_layer)

        elif rel.type.value == "negate":
            # Apply negate: find what DOES match first, then invert
            if rel.distance_m is not None:
                inner = dwithin(candidates, ref_layer, rel.distance_m)
            else:
                inner = intersects(candidates, ref_layer)
            result = negate(inner, result)

        else:
            raise ValueError(f"Unknown relation type: {rel.type.value!r}")

    return result

