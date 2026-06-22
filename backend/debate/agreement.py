"""Agreement Check node: scores how much the Advocate and Enforcer
substantively agree (0-100), independent of exact wording, and -- when they
do agree -- proposes the resolved position directly, with no separate Judge
call needed.
"""

import instructor

from backend.clients.groq_client import DEFAULT_MODEL
from backend.clients.retry_policy import MAX_RETRIES
from backend.debate.prompts import AGREEMENT_CHECK_SYSTEM_PROMPT
from backend.models.debate import AgreementCheck, DebateTurn
from backend.models.routing import ContextBundle

AGREEMENT_THRESHOLD = 70


def check_agreement(
    client: instructor.Instructor,
    content: str,
    bundle: ContextBundle,
    advocate_turn: DebateTurn,
    enforcer_turn: DebateTurn,
    model: str = DEFAULT_MODEL,
) -> AgreementCheck:
    user_message = (
        f"Category: {bundle.category.value}\n"
        f"Severity: {bundle.policy.severity.value}\n\n"
        f"Advocate: position={advocate_turn.position} confidence={advocate_turn.confidence} "
        f"rationale={advocate_turn.rationale}\n"
        f"Enforcer: position={enforcer_turn.position} confidence={enforcer_turn.confidence} "
        f"rationale={enforcer_turn.rationale}"
    )

    return client.chat.completions.create(
        model=model,
        response_model=AgreementCheck,
        max_retries=MAX_RETRIES,
        messages=[
            {"role": "system", "content": AGREEMENT_CHECK_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )


def is_resolved(check: AgreementCheck) -> bool:
    return check.agreement_score >= AGREEMENT_THRESHOLD and check.resolved_position is not None
