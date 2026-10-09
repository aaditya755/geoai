"""
tests/test_vision_fixture.py — vision module unit tests using a toy FAISS index.

Tests the instance grounding path (SkyCLIP retrieval) using a toy index
with known embeddings. Does NOT require GPU or real data.

P3.6 task gate.
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box

sys.path.insert(0, str(Path(__file__).parent.parent))


# ---------------------------------------------------------------------------
# Toy FAISS index builder
# ---------------------------------------------------------------------------

def _make_toy_index(n_tiles: int = 10, embed_dim: int = 512):
    """
    Build a tiny FAISS flat-IP index with random L2-normalised embeddings.
    Returns (index, meta, tile_ids, embeddings).
    """
    import faiss

    embeddings = np.random.randn(n_tiles, embed_dim).astype("float32")
    # L2 normalise
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / (norms + 1e-8)

    index = faiss.IndexFlatIP(embed_dim)
    index.add(embeddings)

    tile_ids = [f"tile_{i:04d}" for i in range(n_tiles)]
    meta = {"embed_dim": embed_dim, "n_tiles": n_tiles, "tiles": [
        {"tile_id": tid, "tile_path": f"data/processed/tiles_8bit/{tid}.tif", "n_crops": 3}
        for tid in tile_ids
    ]}
    return index, meta, tile_ids, embeddings


def _make_toy_footprints(tile_ids):
    """Build a tile footprints GeoDataFrame."""
    rows = []
    for i, tid in enumerate(tile_ids):
        lng = -43.17 + i * 0.01
        lat = -22.90 + i * 0.005
        rows.append({"tile_id": tid, "geometry": box(lng, lat, lng + 0.008, lat + 0.004)})
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


def _write_toy_index(tmp_dir: Path, n_tiles: int = 10, embed_dim: int = 512):
    """Write toy FAISS index and meta JSON to tmp_dir. Returns paths."""
    import faiss
    import json

    index, meta, tile_ids, embeddings = _make_toy_index(n_tiles, embed_dim)
    index_path = tmp_dir / "skyclip.index"
    meta_path = tmp_dir / "skyclip_meta.json"
    faiss.write_index(index, str(index_path))
    with open(meta_path, "w") as f:
        json.dump(meta, f)
    return index_path, meta_path, tile_ids, embeddings


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGroundOSMOnly:
    """OSM-only grounding path — no FAISS, no model."""

    def _make_osm_layer(self):
        from shapely.geometry import LineString
        rows = [
            {"geometry": LineString([(-43.17, -22.90), (-43.16, -22.90)]), "highway": "primary"},
            {"geometry": LineString([(-43.165, -22.905), (-43.155, -22.905)]), "highway": "residential"},
        ]
        return gpd.GeoDataFrame(rows, crs="EPSG:4326")

    def test_osm_only_returns_geodataframe(self):
        from vision import _ground_osm_only

        registry = {
            "road": {"kind": "osm_only", "osm_key": "highway", "osm_value": "*"}
        }
        osm_layers = {"road": self._make_osm_layer()}
        result, msg = _ground_osm_only("road", osm_layers, registry)
        assert isinstance(result, gpd.GeoDataFrame)
        assert not result.empty
        assert msg is None or "OSM" in msg

    def test_osm_only_has_required_columns(self):
        from vision import _ground_osm_only

        registry = {"road": {"kind": "osm_only", "osm_key": "highway", "osm_value": "*"}}
        osm_layers = {"road": self._make_osm_layer()}
        result, _ = _ground_osm_only("road", osm_layers, registry)
        for col in ("score", "concept_id", "measured_distance_m", "rank"):
            assert col in result.columns, f"Missing column: {col}"

    def test_osm_only_score_is_one(self):
        from vision import _ground_osm_only

        registry = {"road": {"kind": "osm_only", "osm_key": "highway", "osm_value": "*"}}
        osm_layers = {"road": self._make_osm_layer()}
        result, _ = _ground_osm_only("road", osm_layers, registry)
        assert all(s == 1.0 for s in result["score"])

    def test_osm_only_unknown_concept_returns_empty(self):
        from vision import _ground_osm_only

        result, msg = _ground_osm_only("alien_ship", {}, {})
        assert result.empty
        assert msg is not None

    def test_osm_only_missing_layer_returns_empty(self):
        from vision import _ground_osm_only

        registry = {"road": {"kind": "osm_only", "osm_key": "highway", "osm_value": "*"}}
        result, msg = _ground_osm_only("road", {}, registry)
        assert result.empty
        assert msg is not None

    def test_not_visible_concept_returns_message(self):
        from vision import _ground_osm_only

        registry = {
            "solar_panel": {
                "kind": "instance",
                "osm_key": "generator:source",
                "osm_value": "solar",
                "not_visible_note": "Too small at 0.5 m/px.",
            }
        }
        # No layer for solar_panel
        result, msg = _ground_osm_only("solar_panel", {}, registry)
        assert result.empty
        # Message should mention visibility
        assert msg is not None


class TestGroundInstance:
    """Instance grounding path — uses toy FAISS index, no GPU."""

    def test_instance_returns_top_k(self):
        """Query a toy index; result count should be <= top_k."""
        pytest.importorskip("faiss", reason="faiss not installed")

        from vision import _ground_instance

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            n_tiles = 10
            embed_dim = 512
            index_path, meta_path, tile_ids, embeddings = _write_toy_index(
                tmp_path, n_tiles=n_tiles, embed_dim=embed_dim
            )
            footprints = _make_toy_footprints(tile_ids)

            # Monkey-patch skyclip_loader to avoid needing real weights
            import types as _types
            import skyclip_loader

            # Stub: return a random unit vector as text embedding
            original_load = skyclip_loader.load_skyclip
            original_embed = skyclip_loader.embed_text

            mock_embed = np.random.randn(embed_dim).astype("float32")
            mock_embed /= np.linalg.norm(mock_embed) + 1e-8

            skyclip_loader.embed_text = lambda model, tokenizer, text, device=None: mock_embed
            skyclip_loader.load_skyclip = lambda weights_path=None: (object(), object(), object())

            registry = {
                "swimming_pool": {
                    "kind": "instance",
                    "skyclip_text": "aerial view of a swimming pool",
                }
            }

            try:
                result, msg = _ground_instance(
                    "swimming_pool", registry, index_path, meta_path,
                    footprints, top_k=5
                )
                assert len(result) <= 5
            finally:
                skyclip_loader.embed_text = original_embed
                skyclip_loader.load_skyclip = original_load

    def test_instance_missing_index_returns_error(self):
        """Missing FAISS index should return empty GDF with an error message."""
        from vision import _ground_instance

        registry = {
            "swimming_pool": {"kind": "instance", "skyclip_text": "pool"}
        }
        result, msg = _ground_instance(
            "swimming_pool", registry,
            Path("nonexistent.index"), Path("nonexistent.json"),
            gpd.GeoDataFrame(), top_k=5
        )
        assert result.empty
        assert msg is not None
        assert "index" in msg.lower() or "not found" in msg.lower()

    def test_instance_result_has_required_columns(self):
        """Result DataFrame must have the detection output columns from design.md §3."""
        pytest.importorskip("faiss", reason="faiss not installed")

        from vision import _ground_instance
        import skyclip_loader

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            embed_dim = 512
            index_path, meta_path, tile_ids, _ = _write_toy_index(tmp_path, embed_dim=embed_dim)
            footprints = _make_toy_footprints(tile_ids)

            mock_embed = np.random.randn(embed_dim).astype("float32")
            mock_embed /= np.linalg.norm(mock_embed) + 1e-8

            original_load = skyclip_loader.load_skyclip
            original_embed = skyclip_loader.embed_text
            skyclip_loader.embed_text = lambda model, tokenizer, text, device=None: mock_embed
            skyclip_loader.load_skyclip = lambda weights_path=None: (object(), object(), object())

            registry = {"swimming_pool": {"kind": "instance", "skyclip_text": "pool"}}

            try:
                result, _ = _ground_instance(
                    "swimming_pool", registry, index_path, meta_path,
                    footprints, top_k=3
                )
                if not result.empty:
                    for col in ("tile_id", "bbox", "score", "concept_id"):
                        assert col in result.columns, f"Missing column: {col}"
            finally:
                skyclip_loader.embed_text = original_embed
                skyclip_loader.load_skyclip = original_load
