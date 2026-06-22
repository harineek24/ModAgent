"""Tests for the LangGraph wiring: fan-out count, conditional routing, and a
full mocked traversal end-to-end. LLM-touching functions (classify,
run_stance_turn, check_agreement, reach_verdict, get_instructor_client) are
monkeypatched so these tests never hit the network -- they validate graph
structure/wiring, not LLM reasoning quality (that's covered by
test_judge.py, test_agreement.py, and test_classification.py).
"""

import pytest
from langgraph.types import Send

from backend.debate import graph as graph_module
from backend.models.category import Category
from backend.models.classification import ClassificationResult
from backend.models.debate import AgreementCheck, DebateTurn, Verdict
from backend.models.routing import ContextBundle


@pytest.fixture
def debatable_bundle(policy_table):
    return ContextBundle(category=Category.HATE_SPEECH, policy=policy_table[Category.HATE_SPEECH], score=0.9)


@pytest.fixture
def tie_safe_bundle(policy_table):
    # SPAM_SCAM has escalate_on_tie=False, so low agreement falls through to the Judge.
    return ContextBundle(category=Category.SPAM_SCAM, policy=policy_table[Category.SPAM_SCAM], score=0.6)


@pytest.fixture
def hard_routed_bundle(policy_table):
    return ContextBundle(category=Category.CSAE, policy=policy_table[Category.CSAE], score=0.95)


# --- dispatch_to_debates fan-out -------------------------------------------

def test_dispatch_to_debates_emits_one_send_per_destination_and_hard_routed(debatable_bundle, hard_routed_bundle):
    state = {
        "content": "some content",
        "destinations": [debatable_bundle],
        "hard_routed": [hard_routed_bundle],
    }
    sends = graph_module.dispatch_to_debates(state)

    assert len(sends) == 2
    assert all(isinstance(s, Send) for s in sends)
    nodes = {s.node for s in sends}
    assert nodes == {"debate_subgraph", "hard_route_verdict"}


def test_dispatch_to_debates_with_no_matches_emits_no_sends():
    state = {"content": "benign content", "destinations": [], "hard_routed": []}
    sends = graph_module.dispatch_to_debates(state)
    assert sends == []


def test_dispatch_to_debates_count_scales_with_multiple_destinations(policy_table):
    bundles = [
        ContextBundle(category=Category.HATE_SPEECH, policy=policy_table[Category.HATE_SPEECH], score=0.9),
        ContextBundle(category=Category.SPAM_SCAM, policy=policy_table[Category.SPAM_SCAM], score=0.6),
        ContextBundle(category=Category.PII_DOXXING, policy=policy_table[Category.PII_DOXXING], score=0.7),
    ]
    state = {"content": "x", "destinations": bundles, "hard_routed": []}
    sends = graph_module.dispatch_to_debates(state)
    assert len(sends) == 3
    assert all(s.node == "debate_subgraph" for s in sends)


# --- hard_route_verdict_node -------------------------------------------------

def test_hard_route_verdict_node_produces_escalated_verdict(hard_routed_bundle):
    result = graph_module.hard_route_verdict_node({"bundle": hard_routed_bundle})
    verdict = result["verdicts"][0]
    assert verdict.category == Category.CSAE
    assert verdict.decision == "escalate"
    assert verdict.escalated is True
    assert verdict.escalation_reason == "non_debatable"


# --- agreement_routing_edge ---------------------------------------------------

def test_agreement_routing_edge_resolves_when_agreement_is_high(debatable_bundle):
    state = {
        "bundle": debatable_bundle,
        "agreement": AgreementCheck(agreement_score=85, resolved_position="restrict", rationale="r"),
    }
    assert graph_module.agreement_routing_edge(state) == "resolve"


def test_agreement_routing_edge_fails_closed_when_escalate_on_tie(debatable_bundle):
    # HATE_SPEECH has escalate_on_tie=True
    state = {
        "bundle": debatable_bundle,
        "agreement": AgreementCheck(agreement_score=20, resolved_position=None, rationale="r"),
    }
    assert graph_module.agreement_routing_edge(state) == "fail_closed_escalate"


def test_agreement_routing_edge_goes_to_judge_when_not_escalate_on_tie(tie_safe_bundle):
    state = {
        "bundle": tie_safe_bundle,
        "agreement": AgreementCheck(agreement_score=20, resolved_position=None, rationale="r"),
    }
    assert graph_module.agreement_routing_edge(state) == "judge"


# --- resolve_node / fail_closed_escalate_node --------------------------------

def test_resolve_node_uses_agreement_check_resolved_position(debatable_bundle):
    state = {
        "bundle": debatable_bundle,
        "advocate_turn": DebateTurn(stance="advocate", position="restrict", confidence=0.9, rationale="r"),
        "enforcer_turn": DebateTurn(stance="enforcer", position="escalate", confidence=0.95, rationale="r"),
        "agreement": AgreementCheck(agreement_score=90, resolved_position="restrict", rationale="aligned"),
    }
    result = graph_module.resolve_node(state)
    verdict = result["verdicts"][0]
    assert verdict.decision == "restrict"
    assert verdict.escalated is False
    assert verdict.agreement_score == 90


def test_resolve_node_marks_escalated_when_resolved_position_is_escalate(debatable_bundle):
    state = {
        "bundle": debatable_bundle,
        "advocate_turn": DebateTurn(stance="advocate", position="escalate", confidence=0.9, rationale="r"),
        "enforcer_turn": DebateTurn(stance="enforcer", position="escalate", confidence=0.95, rationale="r"),
        "agreement": AgreementCheck(agreement_score=95, resolved_position="escalate", rationale="aligned"),
    }
    result = graph_module.resolve_node(state)
    verdict = result["verdicts"][0]
    assert verdict.escalated is True
    assert verdict.escalation_reason == "agreement_escalated"


def test_fail_closed_escalate_node_produces_low_agreement_verdict(debatable_bundle):
    state = {
        "bundle": debatable_bundle,
        "advocate_turn": DebateTurn(stance="advocate", position="allow", confidence=0.9, rationale="r"),
        "enforcer_turn": DebateTurn(stance="enforcer", position="escalate", confidence=0.95, rationale="r"),
        "agreement": AgreementCheck(agreement_score=10, resolved_position=None, rationale="opposed"),
    }
    result = graph_module.fail_closed_escalate_node(state)
    verdict = result["verdicts"][0]
    assert verdict.decision == "escalate"
    assert verdict.escalation_reason == "low_agreement"
    assert verdict.agreement_score == 10


# --- full mocked graph traversal --------------------------------------------

@pytest.fixture
def mocked_graph(monkeypatch, debatable_bundle, hard_routed_bundle):
    scores = {c: 0.0 for c in Category}
    scores[Category.HATE_SPEECH] = 0.9
    scores[Category.CSAE] = 0.95
    fake_classification = ClassificationResult(scores=scores, detected_language="en")

    monkeypatch.setattr(graph_module, "get_instructor_client", lambda api_key=None: object())
    monkeypatch.setattr(graph_module, "classify", lambda client, content: fake_classification)

    def fake_run_stance_turn(client, stance, content, bundle, prior_turns, model=None):
        return DebateTurn(stance=stance, position="restrict", confidence=0.95, rationale="agreed")

    def fake_check_agreement(client, content, bundle, advocate_turn, enforcer_turn, model=None):
        return AgreementCheck(agreement_score=95, resolved_position="restrict", rationale="aligned")

    monkeypatch.setattr(graph_module, "run_stance_turn", fake_run_stance_turn)
    monkeypatch.setattr(graph_module, "check_agreement", fake_check_agreement)

    return graph_module.build_graph().compile()


def test_full_graph_produces_one_verdict_per_routed_category(mocked_graph):
    final_state = mocked_graph.invoke({"content": "some flagged content", "verdicts": [], "transcripts": []})
    verdict_categories = {v.category for v in final_state["verdicts"]}
    assert verdict_categories == {Category.HATE_SPEECH, Category.CSAE}


def test_full_graph_hard_routed_category_is_always_escalated(mocked_graph):
    final_state = mocked_graph.invoke({"content": "some flagged content", "verdicts": [], "transcripts": []})
    csae_verdict = next(v for v in final_state["verdicts"] if v.category == Category.CSAE)
    assert csae_verdict.escalated is True
    assert csae_verdict.decision == "escalate"


def test_full_graph_debatable_category_resolves_via_agreement_check(mocked_graph):
    final_state = mocked_graph.invoke({"content": "some flagged content", "verdicts": [], "transcripts": []})
    hate_verdict = next(v for v in final_state["verdicts"] if v.category == Category.HATE_SPEECH)
    assert hate_verdict.decision == "restrict"
    assert hate_verdict.escalated is False


def test_full_graph_debatable_category_produces_transcript_with_turns(mocked_graph):
    final_state = mocked_graph.invoke({"content": "some flagged content", "verdicts": [], "transcripts": []})
    transcript = next(t for t in final_state["transcripts"] if t.category == Category.HATE_SPEECH)
    assert len(transcript.advocate_turns) == 1
    assert len(transcript.enforcer_turns) == 1


def test_full_graph_hard_routed_category_has_no_transcript(mocked_graph):
    final_state = mocked_graph.invoke({"content": "some flagged content", "verdicts": [], "transcripts": []})
    assert not any(t.category == Category.CSAE for t in final_state["transcripts"])


def test_full_graph_with_benign_content_produces_no_verdicts(monkeypatch):
    benign_classification = ClassificationResult(scores={c: 0.0 for c in Category}, detected_language="en")
    monkeypatch.setattr(graph_module, "get_instructor_client", lambda api_key=None: object())
    monkeypatch.setattr(graph_module, "classify", lambda client, content: benign_classification)

    compiled = graph_module.build_graph().compile()
    final_state = compiled.invoke({"content": "nothing wrong here", "verdicts": [], "transcripts": []})
    assert final_state["verdicts"] == []


def test_full_graph_low_agreement_falls_through_to_judge(monkeypatch, tie_safe_bundle):
    scores = {c: 0.0 for c in Category}
    scores[Category.SPAM_SCAM] = 0.6
    fake_classification = ClassificationResult(scores=scores, detected_language="en")

    monkeypatch.setattr(graph_module, "get_instructor_client", lambda api_key=None: object())
    monkeypatch.setattr(graph_module, "classify", lambda client, content: fake_classification)

    def fake_run_stance_turn(client, stance, content, bundle, prior_turns, model=None):
        position = "allow" if stance == "advocate" else "restrict"
        return DebateTurn(stance=stance, position=position, confidence=0.9, rationale="r")

    def fake_check_agreement(client, content, bundle, advocate_turn, enforcer_turn, model=None):
        return AgreementCheck(agreement_score=15, resolved_position=None, rationale="opposed")

    def fake_reach_verdict(client, content, bundle, advocate_turn, enforcer_turn, model=None):
        return Verdict(
            category=bundle.category, decision="restrict", confidence=0.8, rationale="judge weighed it",
            cited_clauses=[], escalated=False,
        )

    monkeypatch.setattr(graph_module, "run_stance_turn", fake_run_stance_turn)
    monkeypatch.setattr(graph_module, "check_agreement", fake_check_agreement)
    monkeypatch.setattr(graph_module, "reach_verdict", fake_reach_verdict)

    compiled = graph_module.build_graph().compile()
    final_state = compiled.invoke({"content": "borderline content", "verdicts": [], "transcripts": []})
    verdict = next(v for v in final_state["verdicts"] if v.category == Category.SPAM_SCAM)
    assert verdict.decision == "restrict"
    assert verdict.agreement_score == 15
