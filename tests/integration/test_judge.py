"""Tests for the judge node's fail-closed decision logic. The Instructor client
is stubbed since these tests target the branching logic in reach_verdict, not
actual LLM reasoning quality.
"""

import pytest

from backend.debate.judge import reach_verdict
from backend.models.category import Category
from backend.models.debate import DebateTurn, Verdict
from backend.models.routing import ContextBundle


class StubInstructorClient:
    def __init__(self, response=None):
        self.response = response
        self.called = False

        class _Completions:
            def create(_self, **kwargs):
                self.called = True
                return self.response

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def make_bundle(policy_table, category: Category, score: float = 0.8) -> ContextBundle:
    return ContextBundle(category=category, policy=policy_table[category], score=score)


def make_turn(stance: str, position: str, confidence: float) -> DebateTurn:
    return DebateTurn(
        stance=stance,
        position=position,
        confidence=confidence,
        rationale="because",
        cited_clauses=["clause-1"],
    )


def test_non_debatable_category_always_escalates_without_calling_llm(policy_table):
    bundle = make_bundle(policy_table, Category.CSAE)
    client = StubInstructorClient()
    advocate = make_turn("advocate", "allow", 0.9)
    enforcer = make_turn("enforcer", "restrict", 0.9)

    verdict = reach_verdict(client, "content", bundle, advocate, enforcer)

    assert verdict.decision == "escalate"
    assert verdict.escalated is True
    assert client.called is False
    assert verdict.escalation_reason == "non_debatable"


def test_unresolved_disagreement_with_escalate_on_tie_escalates_without_calling_llm(policy_table):
    bundle = make_bundle(policy_table, Category.HATE_SPEECH)  # escalate_on_tie=True
    client = StubInstructorClient()
    advocate = make_turn("advocate", "allow", 0.9)
    enforcer = make_turn("enforcer", "restrict", 0.9)

    verdict = reach_verdict(client, "content", bundle, advocate, enforcer)

    assert verdict.decision == "escalate"
    assert verdict.escalated is True
    assert client.called is False
    assert verdict.confidence == 0.9
    assert verdict.escalation_reason == "position_mismatch"


def test_disagreement_below_confidence_threshold_is_treated_as_unresolved(policy_table):
    bundle = make_bundle(policy_table, Category.HATE_SPEECH)
    client = StubInstructorClient()
    advocate = make_turn("advocate", "allow", 0.5)
    enforcer = make_turn("enforcer", "allow", 0.5)

    verdict = reach_verdict(client, "content", bundle, advocate, enforcer)

    assert verdict.decision == "escalate"
    assert client.called is False
    assert verdict.escalation_reason == "low_confidence"


def test_agreement_calls_llm_and_returns_its_verdict(policy_table):
    bundle = make_bundle(policy_table, Category.HATE_SPEECH)
    expected_verdict = Verdict(
        category=Category.HATE_SPEECH,
        decision="restrict",
        confidence=0.95,
        rationale="both agreed",
        cited_clauses=["clause-1"],
        escalated=False,
    )
    client = StubInstructorClient(response=expected_verdict)
    advocate = make_turn("advocate", "restrict", 0.95)
    enforcer = make_turn("enforcer", "restrict", 0.95)

    verdict = reach_verdict(client, "content", bundle, advocate, enforcer)

    assert client.called is True
    assert verdict == expected_verdict


def test_disagreement_without_escalate_on_tie_falls_through_to_llm(policy_table):
    bundle = make_bundle(policy_table, Category.SPAM_SCAM)  # escalate_on_tie=False
    expected_verdict = Verdict(
        category=Category.SPAM_SCAM,
        decision="allow",
        confidence=0.6,
        rationale="judge resolved it",
        cited_clauses=[],
        escalated=False,
    )
    client = StubInstructorClient(response=expected_verdict)
    advocate = make_turn("advocate", "allow", 0.9)
    enforcer = make_turn("enforcer", "restrict", 0.9)

    verdict = reach_verdict(client, "content", bundle, advocate, enforcer)

    assert client.called is True
    assert verdict == expected_verdict


def test_llm_escalate_decision_gets_judge_escalated_reason(policy_table):
    bundle = make_bundle(policy_table, Category.SPAM_SCAM)  # escalate_on_tie=False
    expected_verdict = Verdict(
        category=Category.SPAM_SCAM,
        decision="escalate",
        confidence=0.7,
        rationale="judge decided to escalate",
        cited_clauses=[],
        escalated=True,
    )
    client = StubInstructorClient(response=expected_verdict)
    advocate = make_turn("advocate", "allow", 0.9)
    enforcer = make_turn("enforcer", "restrict", 0.9)

    verdict = reach_verdict(client, "content", bundle, advocate, enforcer)

    assert verdict.escalation_reason == "judge_escalated"


def test_hard_routed_verdict_cites_the_policy_rubric(policy_table):
    bundle = make_bundle(policy_table, Category.TERRORISM_EXTREMISM)
    client = StubInstructorClient()
    advocate = make_turn("advocate", "allow", 0.9)
    enforcer = make_turn("enforcer", "restrict", 0.9)

    verdict = reach_verdict(client, "content", bundle, advocate, enforcer)

    assert verdict.cited_clauses == [bundle.policy.rubric]
