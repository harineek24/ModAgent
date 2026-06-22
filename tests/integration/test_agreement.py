"""Tests for the Agreement Check node: scores substantive agreement between
Advocate and Enforcer (0-100), independent of exact position wording. The
Instructor client is stubbed since these tests target the wiring, not LLM
reasoning quality.
"""

from backend.debate.agreement import AGREEMENT_THRESHOLD, check_agreement, is_resolved
from backend.models.category import Category
from backend.models.debate import AgreementCheck, DebateTurn
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
    return DebateTurn(stance=stance, position=position, confidence=confidence, rationale="because")


def test_check_agreement_calls_llm_and_returns_its_result(policy_table):
    bundle = make_bundle(policy_table, Category.HATE_SPEECH)
    expected = AgreementCheck(agreement_score=92, resolved_position="restrict", rationale="both agree")
    client = StubInstructorClient(response=expected)
    advocate = make_turn("advocate", "restrict", 0.95)
    enforcer = make_turn("enforcer", "escalate", 0.98)

    result = check_agreement(client, "content", bundle, advocate, enforcer)

    assert client.called is True
    assert result == expected


def test_is_resolved_true_above_threshold_with_position():
    check = AgreementCheck(agreement_score=AGREEMENT_THRESHOLD, resolved_position="restrict", rationale="r")
    assert is_resolved(check) is True


def test_is_resolved_false_below_threshold():
    check = AgreementCheck(agreement_score=AGREEMENT_THRESHOLD - 1, resolved_position="restrict", rationale="r")
    assert is_resolved(check) is False


def test_is_resolved_false_without_resolved_position_even_if_score_high():
    check = AgreementCheck(agreement_score=100, resolved_position=None, rationale="r")
    assert is_resolved(check) is False
