"""
eval.py — precision@K evaluation for GeoLens AI.

Computes precision@K (K=5, 10, 20) over a labelled hold-out annotation set.

[MANUAL] The annotations file (data/annotations/labelled_crops.json) must be
created manually by hand-labelling ~100 crops (task P7.2).

Honest reporting: all numbers are computed from ground truth.
No estimated or made-up accuracy figures are used.

Usage:
    python eval.py [--annotations PATH] [--k 5,10,20]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

ANNOTATIONS_PATH = Path("data/annotations/labelled_crops.json")

# Expected annotation format:
# [
#   {"tile_id": "tile_001", "concept": "swimming_pool", "label": true},
#   ...
# ]


def load_annotations(path: Path) -> List[dict]:
    """Load hand-labelled annotations from JSON."""
    if not path.exists():
        raise FileNotFoundError(
            f"Annotations file not found: {path}\n"
            "Hand-label ~100 crops and save to this path (tasks.md P7.2 [MANUAL])."
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def precision_at_k(ranked_results: List[dict], annotations: List[dict], k: int) -> float:
    """
    Compute precision@K.

    precision@K = (number of relevant items in top-K) / K

    Parameters
    ----------
    ranked_results : list of result dicts from /chat, sorted by rank ascending
    annotations    : list of annotation dicts with tile_id + label (bool)
    k              : cutoff

    Returns
    -------
    Precision@K as a float in [0, 1].
    """
    # Build lookup: tile_id → True/False
    annotation_map = {a["tile_id"]: bool(a["label"]) for a in annotations}

    top_k = ranked_results[:k]
    if not top_k:
        return 0.0

    relevant = sum(
        1 for r in top_k
        if annotation_map.get(r.get("tile_id", ""), False)
    )
    return relevant / k


def evaluate(
    results: List[dict],
    annotations: List[dict],
    ks: List[int] = (5, 10, 20),
) -> dict:
    """
    Compute precision@K for each K.

    Returns a dict {k: precision_at_k}.
    """
    return {k: precision_at_k(results, annotations, k) for k in ks}


def print_table(metrics: dict) -> None:
    """Print a markdown table of precision@K values."""
    print("\n| K  | Precision@K |")
    print("|----|-------------|")
    for k, p in sorted(metrics.items()):
        print(f"| {k:<2} | {p:.4f}      |")
    print()
    print("Note: these numbers are computed from hand-labelled ground truth.")
    print("They reflect precision on the hold-out set only.")


def main(annotations_path: Path, ks: List[int]) -> None:
    """
    Run evaluation against the live API or a saved results file.
    """
    annotations = load_annotations(annotations_path)

    # Try to load saved results; if not present, prompt user to run the pipeline first
    results_path = Path("data/cache/last_eval_results.json")
    if not results_path.exists():
        print(
            "No saved results found at data/cache/last_eval_results.json.\n"
            "Run the pipeline on your test queries and save the results there first.\n"
            "Example:\n"
            "  import json; results = [...]; "
            "  json.dump(results, open('data/cache/last_eval_results.json', 'w'))"
        )
        return

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    metrics = evaluate(results, annotations, ks=ks)
    print_table(metrics)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GeoLens AI precision@K evaluation.")
    parser.add_argument("--annotations", type=Path, default=ANNOTATIONS_PATH)
    parser.add_argument("--k", type=str, default="5,10,20",
                        help="Comma-separated K values, e.g. 5,10,20")
    args = parser.parse_args()
    ks = [int(x.strip()) for x in args.k.split(",")]
    main(args.annotations, ks)
