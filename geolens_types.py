"""
GeoLens AI — shared type definitions.

These types are the single source of truth for data contracts between
planner_agent, vision, spatial_engine, jev_ranker, and app.
Nothing geometric is decided by the LLM; the LLM only produces a Plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ConceptKind(str, Enum):
    INSTANCE = "instance"    # detected via SkyCLIP vision
    OSM_ONLY = "osm_only"   # looked up directly in OSM vector data


class RelationType(str, Enum):
    DWITHIN = "dwithin"
    INTERSECTS = "intersects"
    NEGATE = "negate"        # PROPOSED — only active when FEATURE_NEGATE=true


# ---------------------------------------------------------------------------
# Plan schema
# PROPOSED fields are clearly marked and controlled by feature flags.
# ---------------------------------------------------------------------------

@dataclass
class TargetFilters:
    # PROPOSED: only active when FEATURE_MIN_AREA=true
    min_area_m2: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"min_area_m2": self.min_area_m2}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TargetFilters":
        return cls(min_area_m2=d.get("min_area_m2"))


@dataclass
class Target:
    concept: str
    kind: ConceptKind
    filters: TargetFilters = field(default_factory=TargetFilters)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept": self.concept,
            "kind": self.kind.value,
            "filters": self.filters.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Target":
        return cls(
            concept=d["concept"],
            kind=ConceptKind(d["kind"]),
            filters=TargetFilters.from_dict(d.get("filters") or {}),
        )


@dataclass
class Relation:
    type: RelationType
    reference_concept: str
    distance_m: Optional[float] = None
    # PROPOSED: only active when FEATURE_NEGATE=true
    negate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "reference_concept": self.reference_concept,
            "distance_m": self.distance_m,
            "negate": self.negate,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Relation":
        return cls(
            type=RelationType(d["type"]),
            reference_concept=d["reference_concept"],
            distance_m=d.get("distance_m"),
            negate=bool(d.get("negate", False)),
        )


@dataclass
class Plan:
    target: Target
    relations: List[Relation] = field(default_factory=list)
    limit: Optional[int] = None
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target.to_dict(),
            "relations": [r.to_dict() for r in self.relations],
            "limit": self.limit,
            "session_id": self.session_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Plan":
        return cls(
            target=Target.from_dict(d["target"]),
            relations=[Relation.from_dict(r) for r in d.get("relations", [])],
            limit=d.get("limit"),
            session_id=d.get("session_id"),
        )


# ---------------------------------------------------------------------------
# Detection / result types
# Columns defined here mirror design.md §3 (detection output columns).
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """Raw vision output before spatial filtering."""
    tile_id: str
    bbox: Tuple[float, float, float, float]   # (x1, y1, x2, y2) pixel coords
    score: float                               # SkyCLIP cosine similarity
    concept_id: str
    measured_distance_m: float = float("nan") # filled by spatial_engine
    rank: int = 0                             # filled by jev_ranker

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "bbox": list(self.bbox),
            "score": self.score,
            "concept_id": self.concept_id,
            "measured_distance_m": self.measured_distance_m,
            "rank": self.rank,
        }


@dataclass
class RankedResult:
    """Jev-ranked output row, advisory only."""
    tile_id: str
    bbox: Tuple[float, float, float, float]
    score: float
    concept_id: str
    measured_distance_m: float
    rank: int
    score_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tile_id": self.tile_id,
            "bbox": list(self.bbox),
            "score": self.score,
            "concept_id": self.concept_id,
            "measured_distance_m": self.measured_distance_m,
            "rank": self.rank,
            "score_breakdown": self.score_breakdown,
        }


# ---------------------------------------------------------------------------
# API response type
# ---------------------------------------------------------------------------

@dataclass
class ChatResponse:
    session_id: str
    plan: Plan
    candidates: List[Candidate]
    results: List[RankedResult]
    session_history: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    not_found_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "plan": self.plan.to_dict(),
            "candidates": [c.to_dict() for c in self.candidates],
            "results": [r.to_dict() for r in self.results],
            "session_history": self.session_history,
            "error": self.error,
            "not_found_message": self.not_found_message,
        }
