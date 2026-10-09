"""
tests/test_spatial_engine.py — spatial engine unit tests on toy geometries.

All geometries are in EPSG:32723 (UTM Zone 23S, Rio de Janeiro).
These tests do not require any real data.

P2.2 task gate.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import Point, LineString, Polygon

sys.path.insert(0, str(Path(__file__).parent.parent))

import spatial_engine
from spatial_engine import dwithin, intersects, RIO_CRS

# ---------------------------------------------------------------------------
# Toy geometry fixtures
# ---------------------------------------------------------------------------

def _make_candidates():
    """Three point candidates: A (near road), B (far from road), C (on road)."""
    # A: 50 m from road
    # B: 500 m from road
    # C: right on the road
    points = {
        "A": Point(0, 50),     # 50 m north of road
        "B": Point(0, 500),    # 500 m north
        "C": Point(0, 0),      # on the road
    }
    rows = [
        {"tile_id": name, "bbox": [0.0, 0.0, 1.0, 1.0], "score": 0.9,
         "concept_id": "swimming_pool", "geometry": geom}
        for name, geom in points.items()
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=RIO_CRS)


def _make_road():
    """A road running east-west at y=0."""
    road_geom = LineString([(-1000, 0), (1000, 0)])
    return gpd.GeoDataFrame(
        [{"geometry": road_geom, "highway": "primary"}],
        geometry="geometry",
        crs=RIO_CRS,
    )


def _make_polygon_candidates():
    """Two polygon candidates: one intersects the park, one does not."""
    inside = Polygon([(10, 10), (20, 10), (20, 20), (10, 20)])   # inside park
    outside = Polygon([(200, 200), (300, 200), (300, 300), (200, 300)])  # outside
    rows = [
        {"tile_id": "inside", "bbox": [10.0, 10.0, 20.0, 20.0], "score": 0.8,
         "concept_id": "building", "geometry": inside},
        {"tile_id": "outside", "bbox": [200.0, 200.0, 300.0, 300.0], "score": 0.7,
         "concept_id": "building", "geometry": outside},
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=RIO_CRS)


def _make_park():
    """A park polygon covering (0,0)→(100,100)."""
    park_geom = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    return gpd.GeoDataFrame(
        [{"geometry": park_geom, "leisure": "park"}],
        geometry="geometry",
        crs=RIO_CRS,
    )


# ---------------------------------------------------------------------------
# dwithin tests
# ---------------------------------------------------------------------------

class TestDWithin:

    def test_finds_nearby_candidates(self):
        candidates = _make_candidates()
        road = _make_road()
        result = dwithin(candidates, road, distance_m=100.0)
        tile_ids = set(result["tile_id"].tolist())
        assert "A" in tile_ids, "A is 50 m from road, should be included at 100 m threshold"
        assert "C" in tile_ids, "C is on the road (0 m), should always be included"
        assert "B" not in tile_ids, "B is 500 m away, should be excluded at 100 m threshold"

    def test_excludes_all_beyond_threshold(self):
        candidates = _make_candidates()
        road = _make_road()
        result = dwithin(candidates, road, distance_m=10.0)
        tile_ids = set(result["tile_id"].tolist())
        assert "C" in tile_ids
        assert "A" not in tile_ids
        assert "B" not in tile_ids

    def test_includes_all_within_large_threshold(self):
        candidates = _make_candidates()
        road = _make_road()
        result = dwithin(candidates, road, distance_m=1000.0)
        assert len(result) == 3

    def test_measured_distance_m_column_present(self):
        candidates = _make_candidates()
        road = _make_road()
        result = dwithin(candidates, road, distance_m=200.0)
        assert "measured_distance_m" in result.columns

    def test_measured_distances_are_finite(self):
        candidates = _make_candidates()
        road = _make_road()
        result = dwithin(candidates, road, distance_m=200.0)
        assert all(math.isfinite(d) for d in result["measured_distance_m"])

    def test_measured_distances_are_nonnegative(self):
        candidates = _make_candidates()
        road = _make_road()
        result = dwithin(candidates, road, distance_m=1000.0)
        assert all(d >= 0 for d in result["measured_distance_m"])

    def test_candidate_on_road_has_distance_zero(self):
        candidates = _make_candidates()
        road = _make_road()
        result = dwithin(candidates, road, distance_m=1000.0)
        c_row = result[result["tile_id"] == "C"]
        assert len(c_row) == 1
        assert c_row["measured_distance_m"].iloc[0] == pytest.approx(0.0, abs=1e-6)

    def test_empty_candidates_returns_empty(self):
        empty = gpd.GeoDataFrame(columns=["tile_id", "geometry"], geometry="geometry", crs=RIO_CRS)
        road = _make_road()
        result = dwithin(empty, road, distance_m=100.0)
        assert result.empty


# ---------------------------------------------------------------------------
# intersects tests
# ---------------------------------------------------------------------------

class TestIntersects:

    def test_finds_intersecting_candidate(self):
        candidates = _make_polygon_candidates()
        park = _make_park()
        result = intersects(candidates, park)
        tile_ids = set(result["tile_id"].tolist())
        assert "inside" in tile_ids
        assert "outside" not in tile_ids

    def test_measured_distance_m_is_zero_for_intersects(self):
        candidates = _make_polygon_candidates()
        park = _make_park()
        result = intersects(candidates, park)
        assert all(d == 0.0 for d in result["measured_distance_m"])

    def test_empty_candidates_returns_empty(self):
        empty = gpd.GeoDataFrame(columns=["tile_id", "geometry"], geometry="geometry", crs=RIO_CRS)
        park = _make_park()
        result = intersects(empty, park)
        assert result.empty


# ---------------------------------------------------------------------------
# negate tests
# ---------------------------------------------------------------------------

class TestNegate:

    def test_negate_raises_when_flag_off(self, monkeypatch):
        monkeypatch.setattr(spatial_engine, "FEATURE_NEGATE", False)
        candidates = _make_candidates()
        inner = candidates.head(1)
        with pytest.raises(RuntimeError, match="PROPOSED"):
            spatial_engine.negate(inner, candidates)

    def test_negate_returns_complement_when_flag_on(self, monkeypatch):
        monkeypatch.setattr(spatial_engine, "FEATURE_NEGATE", True)
        candidates = _make_candidates()
        # Pretend only "A" matched the inner relation
        inner = candidates[candidates["tile_id"] == "A"].copy()
        result = spatial_engine.negate(inner, candidates)
        tile_ids = set(result["tile_id"].tolist())
        assert "A" not in tile_ids
        assert "B" in tile_ids
        assert "C" in tile_ids

    def test_negate_all_returns_empty(self, monkeypatch):
        monkeypatch.setattr(spatial_engine, "FEATURE_NEGATE", True)
        candidates = _make_candidates()
        result = spatial_engine.negate(candidates, candidates)
        assert result.empty


# ---------------------------------------------------------------------------
# CRS safety
# ---------------------------------------------------------------------------

class TestCRSSafety:

    def test_no_crs_raises(self):
        candidates = _make_candidates()
        candidates = candidates.set_crs(None, allow_override=True)
        road = _make_road()
        with pytest.raises(ValueError, match="no CRS"):
            dwithin(candidates, road, distance_m=100.0)
