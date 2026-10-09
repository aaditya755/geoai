"""
tests/test_llm_provider_live.py — LIVE integration test for OpenRouter provider.

This test makes a real API call to OpenRouter.
It is OPT-IN — only runs when both:
  OPENROUTER_API_KEY   is set
  OPENROUTER_RUN_LIVE_TESTS=true is set

Run manually:
    OPENROUTER_API_KEY=sk-or-... OPENROUTER_RUN_LIVE_TESTS=true \\
        pytest tests/test_llm_provider_live.py -v -s

Never claim this test passed if it was not actually executed.
Report status honestly in the final validation report.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

LIVE = (
    os.environ.get("OPENROUTER_API_KEY", "").strip()
    and os.environ.get("OPENROUTER_RUN_LIVE_TESTS", "").lower() == "true"
)

skip_if_not_live = pytest.mark.skipif(
    not LIVE,
    reason="Live test skipped. Set OPENROUTER_API_KEY and OPENROUTER_RUN_LIVE_TESTS=true to enable.",
)


@skip_if_not_live
def test_live_openrouter_generates_valid_plan():
    """
    Makes a real OpenRouter API call and verifies the response is a schema-valid plan.

    Reports:
      - Model ID used
      - Whether structured output was accepted
      - The raw response
      - Schema validation outcome
    """
    from llm_provider import OpenRouterPlannerProvider, get_provider_info
    from validate_plan import is_valid_plan, validate_plan

    api_key = os.environ["OPENROUTER_API_KEY"]
    model = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")

    print(f"\n[LIVE] Model: {model}")
    print(f"[LIVE] Provider info: {get_provider_info()}")

    provider = OpenRouterPlannerProvider(api_key=api_key, model=model)

    # Load the real plan schema for structured output
    schema_path = Path(__file__).parent.parent / "schemas" / "plan_schema.json"
    with open(schema_path) as f:
        schema = json.load(f)

    from llm_provider import _SYSTEM_PROMPT  # import after ensuring it's accessible
    # Re-import to avoid circularity
    import llm_provider as _lp

    messages = [
        {"role": "system", "content": _lp._SYSTEM_PROMPT if hasattr(_lp, '_SYSTEM_PROMPT') else
         "You are a spatial query planner. Return only a JSON plan."},
        {"role": "user",   "content": "swimming pools within 100 m of a road"},
    ]

    structured_ok = True
    try:
        raw = provider.generate_plan(messages, response_schema=schema)
        print(f"[LIVE] Structured output response (first 300 chars): {raw[:300]}")
    except Exception as e:
        print(f"[LIVE] Structured output failed: {e}. Retrying without schema.")
        structured_ok = False
        raw = provider.generate_plan(messages, response_schema=None)
        print(f"[LIVE] Plain response (first 300 chars): {raw[:300]}")

    print(f"[LIVE] Structured output accepted: {structured_ok}")

    # Extract and validate
    import re
    text = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    assert start != -1 and end != -1, f"No JSON object found in response: {raw[:300]}"
    plan_dict = json.loads(text[start:end+1])

    print(f"[LIVE] Parsed plan: {json.dumps(plan_dict, indent=2)}")

    assert is_valid_plan(plan_dict), f"Plan failed schema validation: {plan_dict}"
    print("[LIVE] ✓ Schema validation passed")

    assert plan_dict["target"]["concept"] in (
        "swimming_pool", "pool", "pools"
    ), f"Expected pool concept, got: {plan_dict['target']['concept']}"
    print(f"[LIVE] ✓ Concept: {plan_dict['target']['concept']}")

    rels = plan_dict.get("relations", [])
    assert len(rels) >= 1, "Expected at least one spatial relation"
    assert rels[0]["type"] == "dwithin"
    assert rels[0]["distance_m"] == pytest.approx(100.0)
    print(f"[LIVE] ✓ Relation: {rels[0]}")

    print(f"[LIVE] RESULT: PASSED — model={model}, structured_output={structured_ok}")


@skip_if_not_live
def test_live_openrouter_follow_up():
    """Tests that a follow-up 'now within 50 m' amends the previous plan."""
    import planner_agent

    p1, sid = planner_agent.plan("swimming pools within 100 m of a road")
    print(f"\n[LIVE] First plan: {p1.to_dict()}")
    assert p1.relations[0].distance_m == pytest.approx(100.0)

    p2, _ = planner_agent.plan("now within 50 m", session_id=sid)
    print(f"[LIVE] Amended plan: {p2.to_dict()}")
    assert p2.relations[0].distance_m == pytest.approx(50.0), (
        f"Expected 50.0, got {p2.relations[0].distance_m}"
    )
    print("[LIVE] ✓ Follow-up query correctly amended distance")


@skip_if_not_live
def test_live_openrouter_unsupported_concept():
    """Solar panels are invisible; plan must still be schema-valid."""
    import planner_agent
    from validate_plan import is_valid_plan

    p, _ = planner_agent.plan("solar panels on rooftops near a road")
    print(f"\n[LIVE] Unsupported concept plan: {p.to_dict()}")
    assert is_valid_plan(p.to_dict())
    print("[LIVE] ✓ Valid plan for unsupported concept")
