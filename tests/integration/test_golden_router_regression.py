"""Regression suite: runs every case in tests/golden/moderation_cases.json
through the real router. Labels become scores of 1.0/0.0 (no LLM call) --
this tests the router's behavior across real-world label combinations drawn
from a public moderation eval set, at far higher combinatorial coverage than
hand-written cases alone.
"""

import json
from pathlib import Path

import pytest

from backend.models.category import Category
from backend.models.classification import ClassificationResult
from backend.routing.router import route

GOLDEN_PATH = Path(__file__).parent.parent / "golden" / "moderation_cases.json"


def _load_golden_cases() -> list[dict]:
    return json.loads(GOLDEN_PATH.read_text())


def _classification_from_case(case: dict) -> ClassificationResult:
    flagged = set(case["expected_destinations"]) | set(case["expected_hard_routed"])
    scores = {c: (1.0 if c.value in flagged else 0.0) for c in Category}
    return ClassificationResult(scores=scores, detected_language="en")


GOLDEN_CASES = _load_golden_cases()


def test_golden_dataset_is_nonempty():
    assert len(GOLDEN_CASES) > 0


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=lambda c: c["content"][:40])
def test_golden_case_routes_as_expected(policy_table, case):
    classification = _classification_from_case(case)
    result = route(classification, policy_table)

    actual_destinations = sorted(b.category.value for b in result.destinations)
    actual_hard_routed = sorted(b.category.value for b in result.hard_routed)

    assert actual_destinations == sorted(case["expected_destinations"])
    assert actual_hard_routed == sorted(case["expected_hard_routed"])


def test_golden_dataset_never_contains_excluded_labels():
    excluded_categories = {Category.CSAE.value}
    for case in GOLDEN_CASES:
        flagged = set(case["expected_destinations"]) | set(case["expected_hard_routed"])
        assert not (flagged & excluded_categories), f"golden case leaked excluded category: {case['content'][:60]}"


def test_golden_dataset_covers_a_spread_of_categories():
    seen_categories = set()
    for case in GOLDEN_CASES:
        seen_categories.update(case["expected_destinations"])
        seen_categories.update(case["expected_hard_routed"])
    assert len(seen_categories) >= 5
