# owner: ai-evaluation
"""Post-run score distribution analysis for triage scoring.

Computes aggregate statistics from triage output and appends a summary
to data/eval/triage-history.jsonl for trend tracking.  Zero LLM cost.

Usage:
    python -m tests.eval.score_distribution --input data/output/filter-triage-below-threshold.json \
                                             --above-scores 0.92,0.85,0.78
    # --above-scores: comma-separated triage scores of articles that passed threshold
"""

import argparse
import json
import logging
import os
import statistics
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HISTORY_FILE = Path("data/eval/triage-history.jsonl")

# Score tier boundaries
TIERS = [
    ("0.90+", 0.90, 1.01),
    ("0.80-0.89", 0.80, 0.90),
    ("0.70-0.79", 0.70, 0.80),
    ("0.50-0.69", 0.50, 0.70),
    ("<0.50", 0.00, 0.50),
]


def compute_distribution(scores: list[float], threshold: float = 0.70) -> dict:
    """Compute score distribution statistics.

    Args:
        scores: All triage scores from a run (above and below threshold).
        threshold: The inclusion threshold.

    Returns:
        Dictionary with distribution statistics.
    """
    if not scores:
        return {
            "count": 0,
            "above_threshold": 0,
            "below_threshold": 0,
            "tiers": {name: 0 for name, _, _ in TIERS},
        }

    tier_counts = {}
    for name, low, high in TIERS:
        tier_counts[name] = sum(1 for s in scores if low <= s < high)

    return {
        "count": len(scores),
        "mean": round(statistics.mean(scores), 3),
        "median": round(statistics.median(scores), 3),
        "stdev": round(statistics.stdev(scores), 3) if len(scores) > 1 else 0.0,
        "min": round(min(scores), 2),
        "max": round(max(scores), 2),
        "above_threshold": sum(1 for s in scores if s >= threshold),
        "below_threshold": sum(1 for s in scores if s < threshold),
        "tiers": tier_counts,
    }


def append_to_history(distribution: dict, run_date: str | None = None) -> Path:
    """Append a distribution summary to the JSONL history file.

    Args:
        distribution: Output of compute_distribution().
        run_date: ISO date string (defaults to today).

    Returns:
        Path to the history file.
    """
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "date": run_date or datetime.now().strftime("%Y-%m-%d"),
        **distribution,
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return HISTORY_FILE


def main():
    parser = argparse.ArgumentParser(
        description="Compute and log triage score distribution"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to filter-triage-below-threshold.json",
    )
    parser.add_argument(
        "--above-scores",
        default="",
        help="Comma-separated scores of above-threshold articles",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
    )
    args = parser.parse_args()

    # Collect all scores
    scores: list[float] = []

    # Above-threshold scores passed via CLI
    if args.above_scores:
        scores.extend(float(s) for s in args.above_scores.split(",") if s.strip())

    # Below-threshold scores from JSON file
    if os.path.exists(args.input):
        with open(args.input) as f:
            below = json.load(f)
        scores.extend(entry["score"] for entry in below if entry.get("score") is not None)

    dist = compute_distribution(scores, args.threshold)
    path = append_to_history(dist)

    print(json.dumps(dist, indent=2))
    print(f"\nAppended to {path}")


if __name__ == "__main__":
    main()
