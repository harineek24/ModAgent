"""Judge node: invoked only when the Agreement Check finds the Advocate and
Enforcer in genuine, unresolved disagreement (agreement score below
AGREEMENT_THRESHOLD -- see graph.py). Reads the full debate and reaches a
final decision: allow or restrict. May call policy_lookup/clause_lookup
(backend/debate/tools.py) to verify cited wording before trusting it.
"""

import instructor
from groq import Groq

from backend.clients.groq_client import DEFAULT_MODEL
from backend.clients.retry_policy import MAX_RETRIES
from backend.debate.prompts import JUDGE_SYSTEM_PROMPT
from backend.debate.tools import gather_tool_context
from backend.models.debate import DebateTurn, Verdict
from backend.models.routing import ContextBundle


def reach_verdict(
    client: instructor.Instructor,
    raw_client: Groq,
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

    tool_context = gather_tool_context(raw_client, model, JUDGE_SYSTEM_PROMPT, user_message)
    if tool_context:
        user_message += f"\n\nTool lookups you made:\n{tool_context}"

    return client.chat.completions.create(
        model=model,
        response_model=Verdict,
        max_retries=MAX_RETRIES,
        messages=[
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
    )
