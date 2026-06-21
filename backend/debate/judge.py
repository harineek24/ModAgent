"""Judge node: synthesizes a final Verdict from the full debate transcript for
one category. Fail-closed: a genuine tie (disagreement over whether a
violation occurred at all) on an escalate_on_tie category routes straight to
escalation rather than allow. A disagreement only over remedy severity (both
sides agree it's a violation, e.g. "restrict" vs. "escalate") is not treated
as a tie -- it's passed to the LLM Judge to weigh.
"""

import instructor

from backend.clients.groq_client import DEFAULT_MODEL
from backend.clients.retry_policy import MAX_RETRIES
from backend.debate.prompts import JUDGE_SYSTEM_PROMPT
from backend.debate.termination import both_acknowledge_violation, disagreement_reason, turns_agree
from backend.models.debate import DebateTurn, Verdict
from backend.models.routing import ContextBundle


def reach_verdict(
    client: instructor.Instructor,
    content: str,
    bundle: ContextBundle,
    advocate_turn: DebateTurn,
    enforcer_turn: DebateTurn,
    model: str = DEFAULT_MODEL,
) -> Verdict:
    if not bundle.policy.debatable:
        return Verdict(
            category=bundle.category,
            decision="escalate",
            confidence=1.0,
            rationale=f"{bundle.category.value} is non-debatable and hard-routed.",
            cited_clauses=[bundle.policy.rubric],
            escalated=True,
            escalation_reason="non_debatable",
        )

    unresolved = not turns_agree(advocate_turn, enforcer_turn)
    # A real tie (e.g. "allow" vs. "escalate") means the two sides disagree on
    # whether this is even a violation -- that's genuine ambiguity, and
    # escalate_on_tie policy fail-closes on it without an LLM call. But when
    # both sides land on a non-"allow" position (e.g. "restrict" vs.
    # "escalate"), they actually agree a violation occurred and only differ
    # on remedy severity -- that's not a tie, it's a question the Judge is
    # well-suited to weigh, so let it fall through to the LLM call below.
    if unresolved and bundle.policy.escalate_on_tie and not both_acknowledge_violation(advocate_turn, enforcer_turn):
        reason = disagreement_reason(advocate_turn, enforcer_turn)
        rationale = (
            "Advocate and Enforcer reached different positions without resolution; "
            "escalate_on_tie policy applies."
            if reason == "position_mismatch"
            else "Advocate and Enforcer agreed on a position but neither reached the "
            "confidence threshold required to resolve the debate; escalate_on_tie policy applies."
        )
        return Verdict(
            category=bundle.category,
            decision="escalate",
            confidence=min(advocate_turn.confidence, enforcer_turn.confidence),
            rationale=rationale,
            cited_clauses=advocate_turn.cited_clauses + enforcer_turn.cited_clauses,
            escalated=True,
            escalation_reason=reason,
        )

    user_message = (
        f"Content under review:\n{content}\n\n"
        f"Category: {bundle.category.value}\n"
        f"Severity: {bundle.policy.severity.value}\n\n"
        f"Advocate: position={advocate_turn.position} confidence={advocate_turn.confidence} "
        f"rationale={advocate_turn.rationale}\n"
        f"Enforcer: position={enforcer_turn.position} confidence={enforcer_turn.confidence} "
        f"rationale={enforcer_turn.rationale}"
    )

    verdict = client.chat.completions.create(
        model=model,
        response_model=Verdict,
        max_retries=MAX_RETRIES,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
    if verdict.decision == "escalate" and verdict.escalation_reason is None:
        verdict = verdict.model_copy(update={"escalation_reason": "judge_escalated"})
    return verdict
