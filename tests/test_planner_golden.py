"""
tests/test_planner_golden.py — golden query regression tests.

Runs each golden query through the fallback planner and checks the output
matches the expected plan fragments in tests/golden_queries.json.

Does NOT require MISTRAL_API_KEY.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.pop("MISTRAL_API_KEY", None)

import planner_agent
from validate_plan import is_valid_plan

GOLDEN_PATH = Path(__file__).parent / "golden_queries.json"


def load_golden() -> list:
    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


GOLDEN_CASES = load_golden()


def _check_plan(plan, expected: Dict[str, Any]) -> None:
    """Assert plan fields match expected values (only non-null fields checked)."""
    if expected.get("expected_concept"):
        assert plan.target.concept == expected["expected_concept"], (
            f"Expected concept {expected['expected_concept']!r}, got {plan.target.concept!r}"
        )

    if expected.get("expected_kind"):
        assert plan.target.kind.value == expected["expected_kind"], (
            f"Expected kind {expected['expected_kind']!r}, got {plan.target.kind.value!r}"
        )

    if expected.get("expected_limit") is not None:
        assert plan.limit == expected["expected_limit"], (
            f"Expected limit {expected['expected_limit']}, got {plan.limit}"
        )

    if expected.get("expected_relation_type"):
        assert len(plan.relations) >= 1, "Expected at least one relation"
        rel_types = [r.type.value for r in plan.relations]
        assert expected["expected_relation_type"] in rel_types, (
            f"Expected relation type {expected['expected_relation_type']!r} in {rel_types}"
        )

    if expected.get("expected_distance_m") is not None:
        dwithin_rels = [r for r in plan.relations if r.type.value == "dwithin"]
        assert dwithin_rels, "Expected a dwithin relation"
        distances = [r.distance_m for r in dwithin_rels]
        assert expected["expected_distance_m"] in distances, (
            f"Expected distance_m {expected['expected_distance_m']} in {distances}"
        )

    if expected.get("expected_reference_concept"):
        ref_concepts = [r.reference_concept for r in plan.relations]
        assert expected["expected_reference_concept"] in ref_concepts, (
            f"Expected reference_concept {expected['expected_reference_concept']!r} in {ref_concepts}"
        )


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[c["query"] for c in GOLDEN_CASES])
def test_golden_query(case: Dict[str, Any]) -> None:
    """Each golden query must produce a schema-valid plan matching expected fragments."""
    query = case["query"]
    plan, _ = planner_agent.plan(query)

    # Schema validation — fails loudly on any schema violation
    plan_dict = plan.to_dict()
    assert is_valid_plan(plan_dict), (
        f"Plan for query {query!r} is not schema-valid:\n{json.dumps(plan_dict, indent=2)}"
    )

    # Field-level checks
    _check_plan(plan, case)
