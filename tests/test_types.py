"""
tests/test_types.py — verify Plan round-trips through JSON and schema validation.
P0.4 — task gate: this must pass before any further work.
"""

import json
import sys
from pathlib import Path

import pytest

# Ensure repo root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from geolens_types import (
    ConceptKind, Plan, Relation, RelationType, Target, TargetFilters,
)
from validate_plan import is_valid_plan, validate_plan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _minimal_plan_dict():
    return {
        "target": {"concept": "swimming_pool", "kind": "instance"},
        "relations": [],
    }


def _full_plan_dict():
    return {
        "target": {
            "concept": "swimming_pool",
            "kind": "instance",
            "filters": {"min_area_m2": None},
        },
        "relations": [
            {
                "type": "dwithin",
                "reference_concept": "road",
                "distance_m": 100.0,
                "negate": False,
            }
        ],
        "limit": 10,
        "session_id": "test-session-1",
    }


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_minimal_plan_is_valid(self):
        validate_plan(_minimal_plan_dict())

    def test_full_plan_is_valid(self):
        validate_plan(_full_plan_dict())

    def test_missing_target_fails(self):
        d = {"relations": []}
        assert not is_valid_plan(d)

    def test_missing_relations_fails(self):
        d = {"target": {"concept": "pool", "kind": "instance"}}
        assert not is_valid_plan(d)

    def test_invalid_kind_fails(self):
        d = _minimal_plan_dict()
        d["target"]["kind"] = "magic"
        assert not is_valid_plan(d)

    def test_invalid_relation_type_fails(self):
        d = _minimal_plan_dict()
        d["relations"] = [{"type": "nearby", "reference_concept": "road"}]
        assert not is_valid_plan(d)

    def test_negative_distance_fails(self):
        d = _minimal_plan_dict()
        d["relations"] = [{"type": "dwithin", "reference_concept": "road", "distance_m": -5}]
        assert not is_valid_plan(d)

    def test_extra_fields_fail(self):
        d = _minimal_plan_dict()
        d["extra_field"] = "should not be here"
        assert not is_valid_plan(d)

    def test_null_limit_is_valid(self):
        d = _minimal_plan_dict()
        d["limit"] = None
        validate_plan(d)

    def test_osm_only_kind_is_valid(self):
        d = _minimal_plan_dict()
        d["target"]["kind"] = "osm_only"
        validate_plan(d)

    def test_intersects_relation_is_valid(self):
        d = _minimal_plan_dict()
        d["relations"] = [{"type": "intersects", "reference_concept": "park"}]
        validate_plan(d)


# ---------------------------------------------------------------------------
# Round-trip tests
# ---------------------------------------------------------------------------

class TestPlanRoundTrip:

    def test_minimal_plan_roundtrip(self):
        d = _minimal_plan_dict()
        plan = Plan.from_dict(d)
        back = plan.to_dict()
        # Re-validate the round-tripped dict
        validate_plan(back)
        assert plan.target.concept == "swimming_pool"
        assert plan.target.kind == ConceptKind.INSTANCE
        assert plan.relations == []

    def test_full_plan_roundtrip(self):
        d = _full_plan_dict()
        plan = Plan.from_dict(d)
        back = plan.to_dict()
        validate_plan(back)
        assert plan.limit == 10
        assert plan.session_id == "test-session-1"
        assert len(plan.relations) == 1
        rel = plan.relations[0]
        assert rel.type == RelationType.DWITHIN
        assert rel.reference_concept == "road"
        assert rel.distance_m == 100.0

    def test_json_serialise_deserialise(self):
        plan = Plan.from_dict(_full_plan_dict())
        json_str = json.dumps(plan.to_dict())
        plan2 = Plan.from_dict(json.loads(json_str))
        assert plan2.target.concept == plan.target.concept
        assert plan2.relations[0].distance_m == plan.relations[0].distance_m

    def test_osm_only_plan_roundtrip(self):
        d = {
            "target": {"concept": "road", "kind": "osm_only"},
            "relations": [{"type": "intersects", "reference_concept": "park"}],
            "limit": None,
            "session_id": None,
        }
        plan = Plan.from_dict(d)
        validate_plan(plan.to_dict())
        assert plan.target.kind == ConceptKind.OSM_ONLY


# ---------------------------------------------------------------------------
# Proposed fields (schema must accept them when present)
# ---------------------------------------------------------------------------

class TestProposedFields:

    def test_min_area_null_is_valid(self):
        d = _full_plan_dict()
        d["target"]["filters"]["min_area_m2"] = None
        validate_plan(d)

    def test_min_area_positive_is_valid(self):
        d = _full_plan_dict()
        d["target"]["filters"]["min_area_m2"] = 500.0
        validate_plan(d)

    def test_min_area_negative_fails(self):
        d = _full_plan_dict()
        d["target"]["filters"]["min_area_m2"] = -10.0
        assert not is_valid_plan(d)

    def test_negate_false_is_valid(self):
        d = _full_plan_dict()
        d["relations"][0]["negate"] = False
        validate_plan(d)

    def test_negate_true_is_valid(self):
        # The schema allows negate=true; the runtime enforces the feature flag
        d = _full_plan_dict()
        d["relations"][0]["negate"] = True
        validate_plan(d)

