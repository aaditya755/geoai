"""
validate_plan.py — schema validation utility for GeoLens AI plans.

Usage:
    from validate_plan import validate_plan
    plan_dict = {...}
    validate_plan(plan_dict)   # raises jsonschema.ValidationError on failure
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

import jsonschema

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "plan_schema.json"

def _load_schema() -> Dict[str, Any]:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_plan(plan_dict: Dict[str, Any]) -> None:
    """
    Validate a plan dict against the JSON schema.
    Raises jsonschema.ValidationError with a descriptive message on failure.
    """
    schema = _load_schema()
    jsonschema.validate(instance=plan_dict, schema=schema)


def is_valid_plan(plan_dict: Dict[str, Any]) -> bool:
    """Return True if the plan is schema-valid, False otherwise."""
    try:
        validate_plan(plan_dict)
        return True
    except jsonschema.ValidationError:
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python validate_plan.py plan.json")
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        plan = json.load(f)

    try:
        validate_plan(plan)
        print("✓ Plan is valid")
    except jsonschema.ValidationError as e:
        print(f"✗ Plan is invalid: {e.message}")
        sys.exit(1)
