"""Tests for the Judge node. The Judge is now only invoked by the graph when
the Agreement Check has already determined the Advocate and Enforcer are in
genuine, unresolved disagreement -- so reach_verdict() itself just makes the
LLM call and tags judge-initiated escalations. The Instructor client is
stubbed since these tests target that wiring, not actual LLM reasoning
quality.
"""

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


class StubRawClient:
    """Stub for the plain Groq client used for tool-calling. Returns a
    response with no tool_calls, so gather_tool_context() short-circuits
    immediately without making any extra calls.
    """

    def __init__(self):
        class _Message:
            tool_calls = None

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        class _Completions:
            def create(_self, **kwargs):
                return _Response()

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


def test_reach_verdict_calls_llm_and_returns_its_verdict(policy_table):
    bundle = make_bundle(policy_table, Category.HATE_SPEECH)
    expected_verdict = Verdict(
        category=Category.HATE_SPEECH,
        decision="restrict",
        confidence=0.95,
        rationale="judge weighed both arguments",
        cited_clauses=["clause-1"],
        escalated=False,
    )
    client = StubInstructorClient(response=expected_verdict)
    advocate = make_turn("advocate", "allow", 0.6)
    enforcer = make_turn("enforcer", "restrict", 0.6)

    verdict = reach_verdict(client, StubRawClient(), "content", bundle, advocate, enforcer)

    assert client.called is True
    assert verdict == expected_verdict


def test_llm_escalate_decision_gets_judge_escalated_reason(policy_table):
    bundle = make_bundle(policy_table, Category.SPAM_SCAM)
    expected_verdict = Verdict(
        category=Category.SPAM_SCAM,
        decision="escalate",
        confidence=0.7,
        rationale="judge decided to escalate",
        cited_clauses=[],
        escalated=True,
    )
    client = StubInstructorClient(response=expected_verdict)
    advocate = make_turn("advocate", "allow", 0.5)
    enforcer = make_turn("enforcer", "restrict", 0.5)

    verdict = reach_verdict(client, StubRawClient(), "content", bundle, advocate, enforcer)

    assert verdict.escalation_reason == "judge_escalated"


def test_llm_verdict_with_explicit_reason_is_not_overwritten(policy_table):
    bundle = make_bundle(policy_table, Category.SPAM_SCAM)
    expected_verdict = Verdict(
        category=Category.SPAM_SCAM,
        decision="allow",
        confidence=0.9,
        rationale="judge sided with the advocate",
        cited_clauses=[],
        escalated=False,
    )
    client = StubInstructorClient(response=expected_verdict)
    advocate = make_turn("advocate", "allow", 0.5)
    enforcer = make_turn("enforcer", "restrict", 0.5)

    verdict = reach_verdict(client, StubRawClient(), "content", bundle, advocate, enforcer)

    assert verdict.decision == "allow"
    assert verdict.escalation_reason is None
