"""Judge node: synthesizes a final Verdict from the full debate transcript for
one category. Fail-closed: any unresolved disagreement on an escalate_on_tie
category routes to escalation rather than allow.
"""

import instructor

from backend.clients.groq_client import DEFAULT_MODEL
from backend.clients.retry_policy import MAX_RETRIES
from backend.debate.prompts import JUDGE_SYSTEM_PROMPT
from backend.debate.termination import turns_agree
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
        )

    unresolved = not turns_agree(advocate_turn, enforcer_turn)
    if unresolved and bundle.policy.escalate_on_tie:
        return Verdict(
            category=bundle.category,
            decision="escalate",
            confidence=min(advocate_turn.confidence, enforcer_turn.confidence),
            rationale="Advocate and Enforcer disagreed without resolution; escalate_on_tie policy applies.",
            cited_clauses=advocate_turn.cited_clauses + enforcer_turn.cited_clauses,
            escalated=True,
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

    return client.chat.completions.create(
        model=model,
        response_model=Verdict,
        max_retries=MAX_RETRIES,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
