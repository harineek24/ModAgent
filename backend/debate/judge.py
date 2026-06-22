"""Judge node: invoked only when the Agreement Check finds the Advocate and
Enforcer in genuine, unresolved disagreement (agreement score below
AGREEMENT_THRESHOLD, or the category fails closed on ties without even
reaching this node -- see graph.py). Reads the full debate and reaches a
final decision: allow, restrict, or escalate.
"""

import instructor

from backend.clients.groq_client import DEFAULT_MODEL
from backend.clients.retry_policy import MAX_RETRIES
from backend.debate.prompts import JUDGE_SYSTEM_PROMPT
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
