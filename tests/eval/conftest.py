# owner: ai-evaluation
"""Pytest configuration for AI evaluation tests.

Defines custom markers and shared fixtures for the evaluation framework.
"""

import json
import os
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Custom markers
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Register custom markers for eval tests."""
    config.addinivalue_line(
        "markers",
        "eval: evaluation tests requiring ANTHROPIC_API_KEY (deselect with -m 'not eval')",
    )
    config.addinivalue_line(
        "markers",
        "eval_costly: evaluation tests making >20 LLM calls (run manually)",
    )
    config.addinivalue_line(
        "markers",
        "regression: regression tests triggered by prompt file changes",
    )


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EVAL_DIR = Path(__file__).parent
GOLD_STANDARD_DIR = EVAL_DIR / "gold_standard"
GOLDEN_OUTPUTS_DIR = EVAL_DIR / "golden_outputs"
PROJECT_ROOT = EVAL_DIR.parent.parent
CACHE_DIR = PROJECT_ROOT / "data" / "eval" / ".cache"


# ---------------------------------------------------------------------------
# Skip conditions
# ---------------------------------------------------------------------------

requires_api_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def gold_triage_path():
    """Path to the triage gold standard dataset."""
    return GOLD_STANDARD_DIR / "triage_gold.json"


@pytest.fixture
def gold_summary_path():
    """Path to the summary gold standard dataset."""
    return GOLD_STANDARD_DIR / "summary_gold.json"


@pytest.fixture
def must_catch_path():
    """Path to the must-catch article list."""
    return GOLD_STANDARD_DIR / "must_catch.json"


@pytest.fixture
def gold_triage_data(gold_triage_path):
    """Load the triage gold standard dataset."""
    if not gold_triage_path.exists():
        pytest.skip("Triage gold standard dataset not yet populated")
    with open(gold_triage_path) as f:
        data = json.load(f)
    if not data.get("articles"):
        pytest.skip("Triage gold standard dataset has no articles")
    return data


@pytest.fixture
def gold_summary_data(gold_summary_path):
    """Load the summary gold standard dataset."""
    if not gold_summary_path.exists():
        pytest.skip("Summary gold standard dataset not yet populated")
    with open(gold_summary_path) as f:
        data = json.load(f)
    if not data.get("articles"):
        pytest.skip("Summary gold standard dataset has no articles")
    return data
