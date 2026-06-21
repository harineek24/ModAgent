import time

import pytest
from hypothesis import given, strategies as st

from backend.models.category import Category
from backend.models.classification import ClassificationResult
from backend.routing.router import DEFAULT_THRESHOLD, route
from tests.conftest import make_classification


# --- happy path, per category ---------------------------------------------

@pytest.mark.parametrize("category", [c for c in Category if c != Category.BENIGN])
def test_single_category_above_threshold_routes_correctly(policy_table, category):
    classification = make_classification(category, score=0.9)
    result = route(classification, policy_table)

    policy = policy_table[category]
    if policy.debatable:
        assert len(result.destinations) == 1
        assert result.destinations[0].category == category
        assert result.hard_routed == []
    else:
        assert len(result.hard_routed) == 1
        assert result.hard_routed[0].category == category
        assert result.destinations == []
    assert result.is_benign is False


@pytest.mark.parametrize("category", [Category.CSAE, Category.TERRORISM_EXTREMISM, Category.SELF_HARM_SUICIDE])
def test_hard_route_categories_bypass_debate(policy_table, category):
    classification = make_classification(category, score=0.95)
    result = route(classification, policy_table)

    assert any(b.category == category for b in result.hard_routed)
    assert not any(b.category == category for b in result.destinations)


# --- multi-label ------------------------------------------------------------

def test_multiple_categories_above_threshold_all_present(policy_table):
    scores = {c: 0.0 for c in Category}
    scores[Category.HATE_SPEECH] = 0.8
    scores[Category.VIOLENCE_INCITEMENT] = 0.7
    classification = ClassificationResult(scores=scores, detected_language="en")

    result = route(classification, policy_table)
    routed_categories = {b.category for b in result.destinations}
    assert routed_categories == {Category.HATE_SPEECH, Category.VIOLENCE_INCITEMENT}


def test_debatable_and_hard_routed_categories_both_populate(policy_table):
    scores = {c: 0.0 for c in Category}
    scores[Category.HATE_SPEECH] = 0.8
    scores[Category.CSAE] = 0.9
    classification = ClassificationResult(scores=scores, detected_language="en")

    result = route(classification, policy_table)
    assert {b.category for b in result.destinations} == {Category.HATE_SPEECH}
    assert {b.category for b in result.hard_routed} == {Category.CSAE}


# --- benign / boundary -------------------------------------------------------

def test_all_scores_below_threshold_is_benign(policy_table, benign_classification):
    result = route(benign_classification, policy_table)
    assert result.is_benign is True
    assert result.destinations == []
    assert result.hard_routed == []


def test_score_exactly_at_threshold_is_inclusive(policy_table):
    classification = make_classification(Category.SPAM_SCAM, score=DEFAULT_THRESHOLD)
    result = route(classification, policy_table)
    assert any(b.category == Category.SPAM_SCAM for b in result.destinations)


def test_score_just_below_threshold_excluded(policy_table):
    classification = make_classification(Category.SPAM_SCAM, score=DEFAULT_THRESHOLD - 0.01)
    result = route(classification, policy_table)
    assert result.is_benign is True


def test_all_categories_at_max_score(policy_table):
    scores = {c: 1.0 for c in Category}
    classification = ClassificationResult(scores=scores, detected_language="en")
    result = route(classification, policy_table)
    total_routed = len(result.destinations) + len(result.hard_routed)
    assert total_routed == len(Category) - 1  # excludes BENIGN


# --- malformed input ----------------------------------------------------------

def test_empty_scores_dict_is_benign(policy_table):
    classification = ClassificationResult(scores={}, detected_language="en")
    result = route(classification, policy_table)
    assert result.is_benign is True


def test_obfuscation_flag_does_not_suppress_hard_route(policy_table):
    classification = make_classification(Category.CSAE, score=0.9, flags=["obfuscation_detected"])
    result = route(classification, policy_table)
    assert any(b.category == Category.CSAE for b in result.hard_routed)


@pytest.mark.parametrize("bad_score", [-0.1, 1.5, float("nan")])
def test_out_of_range_scores_rejected_by_model(bad_score):
    with pytest.raises(Exception):
        ClassificationResult(scores={Category.HATE_SPEECH: bad_score}, detected_language="en")


# --- determinism / idempotency -----------------------------------------------

@given(score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
def test_router_is_deterministic_for_fixed_input(score):
    from backend.routing.policy_loader import load_policy_table

    policy_table = load_policy_table()
    classification = make_classification(Category.HATE_SPEECH, score=score)
    first = route(classification, policy_table)
    second = route(classification, policy_table)
    assert first == second


# --- performance --------------------------------------------------------------

def test_router_executes_fast_with_no_network_calls(policy_table, benign_classification, monkeypatch):
    def fail_on_network(*args, **kwargs):
        raise AssertionError("Router must not make network calls")

    monkeypatch.setattr("socket.socket.connect", fail_on_network)

    start = time.perf_counter()
    route(benign_classification, policy_table)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 5
