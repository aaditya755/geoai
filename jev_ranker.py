"""
jev_ranker.py — Jev AI ranking adapter for GeoLens AI.

Architecture (from design.md §7):
  - score_local(): deterministic weighted scorer — always available, no API needed.
    Weights: confidence 0.4, proximity 0.3, size 0.3.
    Output is advisory: "local ranking — for human review".
  - JevClient: stub interface for the real Jev AI API.
    Reads: JEV_API_KEY, JEV_API_ENDPOINT, JEV_MODEL, JEV_ENABLED.
    Only active when JEV_ENABLED=true AND JEV_API_KEY is set.
  - rank(): dispatches to JevClient only when both conditions above are met,
    else score_local().

The ranking output is advisory. It is never used to filter or gate geometric
decisions. "Jev AI" label is only shown in the UI after a real, successful
JevClient API invocation (scorer == "jev_ai").

Environment variables:
  JEV_API_KEY      — required for Jev AI calls
  JEV_API_ENDPOINT — Jev AI endpoint (default: https://jev-ai.org/api/v1/systemone/)
  JEV_MODEL        — model identifier (default: jev-1.13)
  JEV_ENABLED      — must be "true" to activate Jev AI (default: false)
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd

JEV_API_KEY: Optional[str] = os.environ.get("JEV_API_KEY")
JEV_ENABLED: bool = os.environ.get("JEV_ENABLED", "false").lower() == "true"
JEV_API_ENDPOINT: str = os.environ.get("JEV_API_ENDPOINT", "https://jev-ai.org/api/v1/systemone/")
JEV_MODEL: str = os.environ.get("JEV_MODEL", "jev-1.13")

_JEV_ACTIVE: bool = JEV_ENABLED and bool(JEV_API_KEY)


# ---------------------------------------------------------------------------
# Local deterministic scorer
# ---------------------------------------------------------------------------

def score_local(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Deterministic weighted scoring over measured criteria.

    Weights:
      confidence  (score column)      : 0.4
      proximity   (measured_distance_m): 0.3  — closer = higher score
      size        (area_m2 if present) : 0.3  — larger = higher score

    All sub-scores are normalised to [0, 1] within this result set.
    Adds columns: jev_score, score_breakdown (dict), rank.
    Returns a new DataFrame sorted by jev_score descending.

    Output is advisory and labelled "ranks for human review".
    """
    if results_df.empty:
        return results_df.copy()

    df = results_df.copy()

    # --- Confidence sub-score (already in [0,1] from SkyCLIP cosine similarity) ---
    conf = df["score"].fillna(0.0).clip(0.0, 1.0)

    # --- Proximity sub-score: closer → higher score ---
    dist = df.get("measured_distance_m", pd.Series(0.0, index=df.index)).fillna(0.0)
    max_dist = dist.max()
    if max_dist > 0:
        proximity = 1.0 - (dist / max_dist)
    else:
        proximity = pd.Series(1.0, index=df.index)

    # --- Size sub-score (from area_m2 column if present) ---
    if "area_m2" in df.columns:
        area = df["area_m2"].fillna(0.0).clip(lower=0.0)
        max_area = area.max()
        size_score = (area / max_area) if max_area > 0 else pd.Series(0.5, index=df.index)
    else:
        # Estimate from bbox if geometry not available
        if "bbox" in df.columns:
            def _bbox_area(bbox) -> float:
                try:
                    b = bbox if isinstance(bbox, list) else list(bbox)
                    return abs((b[2] - b[0]) * (b[3] - b[1]))
                except Exception:
                    return 0.0
            raw_area = df["bbox"].apply(_bbox_area)
            max_area = raw_area.max()
            size_score = (raw_area / max_area) if max_area > 0 else pd.Series(0.5, index=df.index)
        else:
            size_score = pd.Series(0.5, index=df.index)

    # --- Weighted composite ---
    jev = 0.4 * conf + 0.3 * proximity + 0.3 * size_score
    df["jev_score"] = jev.round(4)

    # --- Per-row breakdown ---
    # Label: "local ranking" — NOT "Jev AI". Jev AI is shown only after a
    # real, successful JevClient API invocation (addendum §5).
    df["score_breakdown"] = [
        {
            "confidence": round(float(c), 4),
            "proximity": round(float(p), 4),
            "size": round(float(s), 4),
            "scorer": "local",
            "note": "local ranking — for human review",
        }
        for c, p, s in zip(conf, proximity, size_score)
    ]

    # --- Rank (1-indexed, lower is better) ---
    df = df.sort_values("jev_score", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    return df


# ---------------------------------------------------------------------------
# JevClient stub
# ---------------------------------------------------------------------------

class JevClient:
    """
    Interface stub for the real Jev AI ranking API.

    Endpoint: JEV_API_ENDPOINT (default: https://jev-ai.org/api/v1/systemone/)
    Model:    JEV_MODEL        (default: jev-1.13)

    The real API request/response schema for this endpoint has not been
    verified at implementation time. This stub falls back to score_local()
    until the schema is confirmed and implemented.

    To activate:
      1. Set JEV_ENABLED=true in .env
      2. Set JEV_API_KEY to a valid key
      3. Implement the actual API call below once the schema is confirmed
    """

    def __init__(self, api_key: str):
        # API key stored for use in headers only — never logged or returned to client
        self._api_key = api_key
        self._endpoint = JEV_API_ENDPOINT
        self._model = JEV_MODEL

    def rank(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Call the Jev AI ranking API.

        TODO: implement real API call once the Jev AI systemone endpoint
        request/response schema is confirmed. Current state: stub only.

        The stub falls back to score_local() and warns. Results are labelled
        "local" not "jev_ai" until a real successful call is made.
        """
        import warnings
        warnings.warn(
            f"JevClient.rank() is a stub — real endpoint schema not yet implemented. "
            f"Endpoint: {self._endpoint}, Model: {self._model}. "
            "Falling back to local scorer.",
            UserWarning,
            stacklevel=2,
        )
        return score_local(results_df)


# ---------------------------------------------------------------------------
# Public dispatcher
# ---------------------------------------------------------------------------

def rank(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Rank results.

    Dispatches to JevClient only when JEV_ENABLED=true AND JEV_API_KEY is set.
    Otherwise uses local deterministic scorer.

    The ranking source is reported in score_breakdown["scorer"]:
      "local"  — deterministic local scorer (always available)
      "jev_ai" — real Jev AI API (only after a real successful invocation)

    Output is advisory. Never used to filter or gate geometric decisions.
    Do NOT label results as "Jev AI" in the UI unless scorer == "jev_ai".
    """
    if _JEV_ACTIVE:
        try:
            client = JevClient(api_key=JEV_API_KEY)
            return client.rank(results_df)
        except Exception as e:
            import warnings
            warnings.warn(
                f"JevClient.rank() failed ({e}); falling back to local scorer.",
                UserWarning,
                stacklevel=2,
            )
    elif JEV_API_KEY and not JEV_ENABLED:
        import warnings
        warnings.warn(
            "JEV_API_KEY is set but JEV_ENABLED=false — using local scorer. "
            "Set JEV_ENABLED=true to activate Jev AI ranking.",
            UserWarning,
            stacklevel=2,
        )

    return score_local(results_df)
