"""
tests/test_planner.py — planner agent unit tests.

Tests the fallback rule-based planner and schema validation.
Does NOT require MISTRAL_API_KEY (uses fallback only).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure no real API key is used in tests
os.environ.pop("MISTRAL_API_KEY", None)

import planner_agent
from geolens_types import ConceptKind, RelationType
from validate_plan import is_valid_plan


class TestFallbackPlanner:

    def test_swimming_pool_within_road(self):
        p, sid = planner_agent.plan("swimming pools within 100 m of a road")
        assert p.target.concept == "swimming_pool"
        assert p.target.kind == ConceptKind.INSTANCE
        assert len(p.relations) == 1
        assert p.relations[0].type == RelationType.DWITHIN
        assert p.relations[0].distance_m == 100.0
        assert p.relations[0].reference_concept == "road"

    def test_road_osm_only_kind(self):
        p, _ = planner_agent.plan("show me all roads")
        assert p.target.kind == ConceptKind.OSM_ONLY

    def test_limit_extracted(self):
        p, _ = planner_agent.plan("top 10 buildings near a park")
        assert p.limit == 10

    def test_plan_is_schema_valid(self):
        p, _ = planner_agent.plan("swimming pools within 200 m of a road")
        assert is_valid_plan(p.to_dict())

    def test_follow_up_updates_distance(self):
        p1, sid = planner_agent.plan("swimming pools within 100 m of a road")
        p2, _ = planner_agent.plan("now within 50 m", session_id=sid)
        assert p2.relations[0].distance_m == 50.0

    def test_follow_up_updates_limit(self):
        p1, sid = planner_agent.plan("swimming pools within 100 m of a road")
        p2, _ = planner_agent.plan("only the top 5", session_id=sid)
        assert p2.limit == 5

    def test_session_history_grows(self):
        _, sid = planner_agent.plan("swimming pools within 100 m of a road")
        planner_agent.plan("now within 50 m", session_id=sid)
        history = planner_agent.get_session_history(sid)
        assert len(history) == 2

    def test_new_session_per_call(self):
        _, sid1 = planner_agent.plan("swimming pools")
        _, sid2 = planner_agent.plan("roads near parks")
        assert sid1 != sid2

    def test_solar_panel_still_produces_valid_plan(self):
        """Solar panels are invisible but the planner should still return a valid plan."""
        p, _ = planner_agent.plan("solar panels on rooftops")
        assert is_valid_plan(p.to_dict())

    def test_intersects_relation(self):
        p, _ = planner_agent.plan("buildings near parks")
        assert any(r.type == RelationType.INTERSECTS for r in p.relations)

