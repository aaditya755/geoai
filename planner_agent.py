"""
planner_agent.py — natural language → schema-validated Plan JSON.

The LLM writes ONLY a JSON plan. No geometric decisions are made here.
All geometry happens in spatial_engine.py.

Two paths:
  1. OpenRouter API (when OPENROUTER_API_KEY is set) — real LLM call via llm_provider.py.
  2. Rule-based fallback planner — always available, no API key needed.

The provider interface (LLMPlannerProvider) is defined in llm_provider.py.
Switching to a different LLM requires only implementing that interface there;
planner_agent.py does not change.

Session support:
  - In-memory session store (dict keyed by session_id).
  - Follow-up queries (e.g. "now within 50 m") amend the previous plan.
  - Planner always works in English; translate.py handles non-English input upstream.

PROPOSED fields (feature-flagged):
  - relations[].negate  : FEATURE_NEGATE env var
  - target.filters.min_area_m2 : FEATURE_MIN_AREA env var
"""

from __future__ import annotations

import json
import os
import re
import uuid
from typing import Dict, Optional, Tuple

from validate_plan import validate_plan
from geolens_types import Plan, Target, Relation, ConceptKind, RelationType, TargetFilters
from llm_provider import LLMPlannerProvider, ProviderError, get_provider

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# OPENROUTER_API_KEY and OPENROUTER_MODEL are read inside llm_provider.py.
# planner_agent.py never reads raw API keys.

FEATURE_NEGATE = os.environ.get("FEATURE_NEGATE", "false").lower() == "true"
FEATURE_MIN_AREA = os.environ.get("FEATURE_MIN_AREA", "false").lower() == "true"

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------

_sessions: Dict[str, Dict] = {}  # session_id → {plan, history}


def _new_session_id() -> str:
    return str(uuid.uuid4())


def get_session(session_id: str) -> Optional[Dict]:
    return _sessions.get(session_id)


def save_session(session_id: str, plan: Plan, query: str) -> None:
    if session_id not in _sessions:
        _sessions[session_id] = {"history": []}
    _sessions[session_id]["plan"] = plan.to_dict()
    _sessions[session_id]["history"].append({"query": query, "plan": plan.to_dict()})


# ---------------------------------------------------------------------------
# LLM-backed planner (OpenRouter via llm_provider.py)
# ---------------------------------------------------------------------------

# Load the plan schema once for use in structured output requests.
_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schemas", "plan_schema.json")
_PLAN_SCHEMA: Optional[dict] = None

def _get_plan_schema() -> Optional[dict]:
    """Load and cache the plan JSON schema for structured output requests."""
    global _PLAN_SCHEMA
    if _PLAN_SCHEMA is None:
        try:
            with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
                _PLAN_SCHEMA = json.load(f)
        except (OSError, json.JSONDecodeError):
            _PLAN_SCHEMA = None
    return _PLAN_SCHEMA


_SYSTEM_PROMPT = """You are a spatial query planner for GeoLens AI.
Your job is to convert a natural language query about aerial imagery into a JSON plan.

Rules:
- Write ONLY valid JSON matching the schema. No prose, no explanation, no markdown fences.
- Use "osm_only" for roads, parks, rivers, named areas.
- Use "instance" for visually detectable objects (pools, buildings, parking lots, schools, hospitals, solar panels).
- For "within X metres of Y": type = "dwithin", distance_m = X (number).
- For "intersecting Y" or "near Y": type = "intersects".
- Unsupported/invisible concepts (solar panels, narrow drains): produce a valid plan; the system reports "not found".
- Do not invent OSM keys, column names, file paths, or distance values not stated in the query.
- Copy session_id from the user message if provided, else null.
- Output only the JSON object — no other text."""

_AMEND_SYSTEM_PROMPT = """You are amending an existing spatial query plan for GeoLens AI.
Given the previous plan JSON and a follow-up query, output a new COMPLETE plan JSON
with only the changed fields updated. Copy all unchanged fields verbatim.
Output only the JSON object — no prose, no markdown fences."""


def _extract_json(text: str) -> dict:
    """Extract JSON from a string that may contain markdown fences or surrounding text."""
    # Strip ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip().rstrip("`").strip()
    # If the model wrapped the JSON in surrounding text, find the first { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _plan_dict_postprocess(plan_dict: dict, session_id: Optional[str]) -> dict:
    """Strip PROPOSED fields when feature flags are off; set session_id."""
    if session_id:
        plan_dict["session_id"] = session_id
    if not FEATURE_NEGATE:
        for rel in plan_dict.get("relations", []):
            rel.pop("negate", None)
    if not FEATURE_MIN_AREA:
        filters = plan_dict.get("target", {}).get("filters", {})
        if filters:
            filters.pop("min_area_m2", None)
    return plan_dict


def _call_provider(
    provider: LLMPlannerProvider,
    messages: list,
    use_structured_output: bool = True,
) -> str:
    """
    Call the provider. First attempts structured output (json_schema).
    If that fails with a non-retryable provider error that may indicate
    missing parameter support, falls back to plain-text JSON request.
    """
    schema = _get_plan_schema() if use_structured_output else None
    try:
        return provider.generate_plan(messages, response_schema=schema)
    except ProviderError as e:
        # Only retry without structured output for errors that may indicate
        # the endpoint doesn't support response_format (typically 4xx excluding auth).
        # Auth errors (401/403) and rate limits (429) are re-raised immediately.
        if (not e.retryable
                and use_structured_output
                and e.status_code not in (401, 403, 429)):
            import warnings
            warnings.warn(
                f"Structured output request failed ({e}); retrying without response_format.",
                UserWarning, stacklevel=3,
            )
            return provider.generate_plan(messages, response_schema=None)
        raise


def _plan_from_provider(
    provider: LLMPlannerProvider,
    query: str,
    session_id: Optional[str] = None,
) -> Plan:
    """Call the LLM provider and return a validated Plan."""
    user_content = query
    if session_id:
        user_content = f"session_id: {session_id}\n{query}"

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": user_content},
    ]

    raw = _call_provider(provider, messages)
    plan_dict = _extract_json(raw)
    plan_dict = _plan_dict_postprocess(plan_dict, session_id)
    validate_plan(plan_dict)   # always validate locally — never trust the model alone
    return Plan.from_dict(plan_dict)


def _amend_from_provider(
    provider: LLMPlannerProvider,
    previous_plan: Plan,
    follow_up_query: str,
) -> Plan:
    """Call the LLM provider to amend a previous plan."""
    messages = [
        {"role": "system", "content": _AMEND_SYSTEM_PROMPT},
        {"role": "user",   "content": (
            f"Previous plan:\n{json.dumps(previous_plan.to_dict(), indent=2)}\n\n"
            f"Follow-up: {follow_up_query}\n\nOutput the amended plan JSON only."
        )},
    ]

    raw = _call_provider(provider, messages)
    plan_dict = _extract_json(raw)
    validate_plan(plan_dict)
    return Plan.from_dict(plan_dict)


# ---------------------------------------------------------------------------
# Rule-based fallback planner
# ---------------------------------------------------------------------------

# Concept vocabulary: maps keyword → (concept_id, kind)
# Ordered by specificity (longer/more-specific phrases first).
_CONCEPT_VOCAB = [
    ("swimming pool",       "swimming_pool",   "instance"),
    ("swimming pools",      "swimming_pool",   "instance"),
    ("pool",                "swimming_pool",   "instance"),
    ("pools",               "swimming_pool",   "instance"),
    ("parking lot",         "parking_lot",     "instance"),
    ("parking lots",        "parking_lot",     "instance"),
    ("solar panel",         "solar_panel",     "instance"),
    ("solar panels",        "solar_panel",     "instance"),
    ("narrow drain",        "narrow_drain",    "osm_only"),
    ("narrow drains",       "narrow_drain",    "osm_only"),
    ("green area",          "green_area",      "osm_only"),
    ("green areas",         "green_area",      "osm_only"),
    ("primary road",        "primary_road",    "osm_only"),
    ("primary roads",       "primary_road",    "osm_only"),
    ("residential road",    "residential_road","osm_only"),
    ("residential roads",   "residential_road","osm_only"),
    ("residential street",  "residential_road","osm_only"),
    ("residential streets", "residential_road","osm_only"),
    ("parking",             "parking_lot",     "instance"),
    ("hospital",            "hospital",        "instance"),
    ("hospitals",           "hospital",        "instance"),
    ("school",              "school",          "instance"),
    ("schools",             "school",          "instance"),
    ("building",            "building",        "instance"),
    ("buildings",           "building",        "instance"),
    ("highway",             "road",            "osm_only"),
    ("drain",               "narrow_drain",    "osm_only"),
    ("drains",              "narrow_drain",    "osm_only"),
    ("street",              "road",            "osm_only"),
    ("streets",             "road",            "osm_only"),
    ("roads",               "road",            "osm_only"),
    ("road",                "road",            "osm_only"),
    ("parks",               "park",            "osm_only"),
    ("park",                "park",            "osm_only"),
]

def _find_concept(text: str):
    """Find the first matching concept in text. Returns (concept_id, kind) or (None, None)."""
    text_lower = text.lower()
    for kw, concept_id, kind in _CONCEPT_VOCAB:
        if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
            return concept_id, kind
    return None, None

# Split patterns — everything before the relation keyword is the target clause,
# everything after is the reference clause.
_SPLIT_PATTERNS = [
    re.compile(r'\bwithin\s+\d+', re.IGNORECASE),
    re.compile(r'\bnear\b', re.IGNORECASE),
    re.compile(r'\bnearby\b', re.IGNORECASE),
    re.compile(r'\bintersecting\b', re.IGNORECASE),
    re.compile(r'\badjacent to\b', re.IGNORECASE),
    re.compile(r'\bclose to\b', re.IGNORECASE),
]

def _split_query(query: str):
    """
    Split query into (target_clause, reference_clause).
    Finds the earliest-occurring relation keyword in the query and splits there.
    Returns (query, '') if no relation keyword found.
    """
    best_pos = len(query)
    best_match = None
    for pat in _SPLIT_PATTERNS:
        m = pat.search(query)
        if m and m.start() < best_pos:
            best_pos = m.start()
            best_match = m
    if best_match:
        return query[:best_match.start()].strip(), query[best_match.start():].strip()
    return query, ''

_DISTANCE_PATTERN = re.compile(r"within\s+(\d+(?:\.\d+)?)\s*m(?:etres?|eters?)?", re.IGNORECASE)
_LIMIT_PATTERN = re.compile(r"(?:top|only|first)\s+(\d+)", re.IGNORECASE)
_AREA_PATTERN = re.compile(r"larger\s+than\s+(\d+(?:,\d+)*)\s*(?:sq\.?\s*m|m2|square\s+metres?)", re.IGNORECASE)


def _fallback_plan(query: str, session_id: Optional[str] = None) -> Plan:
    """
    Rule-based fallback planner. Used when MISTRAL_API_KEY is not set or Mistral fails.

    Strategy:
      1. Split the query at the relation keyword (near/within/intersecting).
      2. Find the target concept in the target clause (before the split).
      3. Find the reference concept in the reference clause (after the split).
      4. Parse distance (dwithin) or default to intersects.
    """
    target_clause, ref_clause = _split_query(query)
    full_lower = query.lower()

    # Find target concept — search target clause first, fall back to full query
    target_concept, target_kind = _find_concept(target_clause) if target_clause else (None, None)
    if target_concept is None:
        target_concept, target_kind = _find_concept(query)
    if target_concept is None:
        target_concept, target_kind = "building", "instance"

    # Find reference concept — search reference clause only
    ref_concept_id = None
    if ref_clause:
        ref_cid, _ = _find_concept(ref_clause)
        if ref_cid and ref_cid != target_concept:
            ref_concept_id = ref_cid

    # Parse distance
    relations = []
    dist_match = _DISTANCE_PATTERN.search(query)

    if dist_match and ref_concept_id:
        distance_m = float(dist_match.group(1))
        relations.append(Relation(
            type=RelationType.DWITHIN,
            reference_concept=ref_concept_id,
            distance_m=distance_m,
        ))
    elif ref_concept_id:
        relations.append(Relation(
            type=RelationType.INTERSECTS,
            reference_concept=ref_concept_id,
        ))

    # Find limit
    limit = None
    limit_match = _LIMIT_PATTERN.search(query)
    if limit_match:
        limit = int(limit_match.group(1))

    # Find min_area (PROPOSED — only if flag enabled)
    filters = TargetFilters()
    if FEATURE_MIN_AREA:
        area_match = _AREA_PATTERN.search(query)
        if area_match:
            filters.min_area_m2 = float(area_match.group(1).replace(",", ""))

    plan_dict = Plan(
        target=Target(
            concept=target_concept,
            kind=ConceptKind(target_kind),
            filters=filters,
        ),
        relations=relations,
        limit=limit,
        session_id=session_id,
    ).to_dict()

    validate_plan(plan_dict)
    return Plan.from_dict(plan_dict)


def _amend_fallback(previous_plan: Plan, follow_up_query: str) -> Plan:
    """
    Rule-based follow-up amendment.
    Updates distance or limit if found; preserves all other fields.
    """
    query_lower = follow_up_query.lower()
    amended = Plan.from_dict(previous_plan.to_dict())

    # Update distance
    dist_match = _DISTANCE_PATTERN.search(follow_up_query)
    if dist_match:
        new_dist = float(dist_match.group(1))
        for rel in amended.relations:
            if rel.type == RelationType.DWITHIN:
                rel.distance_m = new_dist

    # Update limit
    limit_match = re.search(r"(?:top|only|first)\s+(\d+)", query_lower)
    if limit_match:
        amended.limit = int(limit_match.group(1))

    # Update min_area (PROPOSED)
    if FEATURE_MIN_AREA:
        area_match = _AREA_PATTERN.search(follow_up_query)
        if area_match:
            amended.target.filters.min_area_m2 = float(area_match.group(1).replace(",", ""))

    validate_plan(amended.to_dict())
    return amended


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def plan(query: str, session_id: Optional[str] = None) -> Tuple[Plan, str]:
    """
    Convert a natural language query to a validated Plan.

    Parameters
    ----------
    query      : natural language query (always in English; translate.py handles other langs)
    session_id : existing session ID for follow-ups, or None to start a new session

    Returns
    -------
    (Plan, session_id)
    """
    if session_id is None:
        session_id = _new_session_id()

    # Check for follow-up
    session = get_session(session_id)
    if session and session.get("plan"):
        previous_plan = Plan.from_dict(session["plan"])
        result_plan = _amend(previous_plan, query)
    else:
        result_plan = _generate(query, session_id)

    save_session(session_id, result_plan, query)
    return result_plan, session_id


def _generate(query: str, session_id: str) -> Plan:
    """
    Generate a new plan (not a follow-up).

    Tries OpenRouter provider first (when OPENROUTER_API_KEY is set).
    Falls back to rule-based planner on any provider failure.
    The plan_source metadata is available via get_session_history().
    """
    provider = get_provider()
    if provider is not None:
        try:
            return _plan_from_provider(provider, query, session_id)
        except (ProviderError, Exception) as e:
            import warnings
            warnings.warn(
                f"OpenRouter provider failed ({type(e).__name__}: {e}); "
                "falling back to rule-based planner.",
                UserWarning, stacklevel=3,
            )
    return _fallback_plan(query, session_id)


def _amend(previous_plan: Plan, follow_up_query: str) -> Plan:
    """
    Amend an existing plan based on a follow-up query.

    Tries OpenRouter provider first, falls back to rule-based amendment.
    """
    provider = get_provider()
    if provider is not None:
        try:
            return _amend_from_provider(provider, previous_plan, follow_up_query)
        except (ProviderError, Exception) as e:
            import warnings
            warnings.warn(
                f"OpenRouter provider amendment failed ({type(e).__name__}: {e}); "
                "falling back to rule-based amendment.",
                UserWarning, stacklevel=3,
            )
    return _amend_fallback(previous_plan, follow_up_query)


def get_session_history(session_id: str) -> list:
    """Return the query/plan history for a session."""
    session = get_session(session_id)
    if session:
        return session.get("history", [])
    return []

