"""
tests/test_jev_ranker.py — Jev ranker unit tests.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from jev_ranker import rank, score_local


def _make_results():
    return pd.DataFrame([
        {"tile_id": "A", "bbox": [0, 0, 10, 10], "score": 0.9, "concept_id": "pool",
         "measured_distance_m": 10.0},
        {"tile_id": "B", "bbox": [0, 0, 5, 5], "score": 0.5, "concept_id": "pool",
         "measured_distance_m": 200.0},
        {"tile_id": "C", "bbox": [0, 0, 20, 20], "score": 0.7, "concept_id": "pool",
         "measured_distance_m": 50.0},
    ])


class TestScoreLocal:

    def test_returns_dataframe(self):
        df = score_local(_make_results())
        assert isinstance(df, pd.DataFrame)

    def test_adds_jev_score_column(self):
        df = score_local(_make_results())
        assert "jev_score" in df.columns

    def test_adds_rank_column(self):
        df = score_local(_make_results())
        assert "rank" in df.columns

    def test_adds_score_breakdown(self):
        df = score_local(_make_results())
        assert "score_breakdown" in df.columns
        breakdown = df.iloc[0]["score_breakdown"]
        assert "confidence" in breakdown
        assert "proximity" in breakdown
        assert "size" in breakdown

    def test_rank_is_1_indexed(self):
        df = score_local(_make_results())
        assert df["rank"].min() == 1

    def test_ranks_are_unique(self):
        df = score_local(_make_results())
        assert df["rank"].nunique() == len(df)

    def test_sorted_by_jev_score_descending(self):
        df = score_local(_make_results())
        scores = df["jev_score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_high_confidence_nearby_ranks_first(self):
        """A (high score, close) should rank above B (low score, far)."""
        df = score_local(_make_results())
        rank_a = df[df["tile_id"] == "A"]["rank"].iloc[0]
        rank_b = df[df["tile_id"] == "B"]["rank"].iloc[0]
        assert rank_a < rank_b

    def test_jev_scores_in_valid_range(self):
        df = score_local(_make_results())
        assert all(0.0 <= s <= 1.0 for s in df["jev_score"])

    def test_empty_dataframe_returns_empty(self):
        empty = pd.DataFrame(columns=["tile_id", "bbox", "score", "measured_distance_m"])
        result = score_local(empty)
        assert result.empty

    def test_score_breakdown_contains_note(self):
        df = score_local(_make_results())
        breakdown = df.iloc[0]["score_breakdown"]
        assert "note" in breakdown
        assert "human review" in breakdown["note"].lower()


class TestRankDispatch:

    def test_rank_fallback_without_key(self, monkeypatch):
        import jev_ranker
        monkeypatch.setattr(jev_ranker, "JEV_API_KEY", None)
        monkeypatch.setattr(jev_ranker, "_JEV_ACTIVE", False)
        df = rank(_make_results())
        assert "jev_score" in df.columns

    def test_rank_fallback_when_disabled(self, monkeypatch):
        """JEV_API_KEY set but JEV_ENABLED=false → local scorer."""
        import jev_ranker
        monkeypatch.setattr(jev_ranker, "JEV_API_KEY", "test-key")
        monkeypatch.setattr(jev_ranker, "JEV_ENABLED", False)
        monkeypatch.setattr(jev_ranker, "_JEV_ACTIVE", False)
        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            df = rank(_make_results())
        assert "jev_score" in df.columns
        # Should warn that key is set but JEV_ENABLED=false
        warning_msgs = [str(x.message) for x in w]
        assert any("JEV_ENABLED=false" in m for m in warning_msgs)

    def test_scorer_label_is_local(self):
        df = score_local(_make_results())
        assert df.iloc[0]["score_breakdown"]["scorer"] == "local"
