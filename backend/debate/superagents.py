"""Superagent nodes: each is an LLM-boundary call producing one DebateTurn for a
given stance, scoped to a single category's ContextBundle. Each stance may
optionally call policy_lookup/clause_lookup (backend/debate/tools.py) before
committing to a position, grounding its rationale in real rubric/example text
instead of recalling it from the prompt alone.
"""

import instructor
from groq import Groq

from backend.clients.groq_client import DEFAULT_MODEL
from backend.clients.retry_policy import MAX_RETRIES
from backend.debate.prompts import ADVOCATE_SYSTEM_PROMPT, ENFORCER_SYSTEM_PROMPT
from backend.debate.tools import gather_tool_context
from backend.models.debate import DebateTurn
from backend.models.routing import ContextBundle

STANCE_PROMPTS = {
    "advocate": ADVOCATE_SYSTEM_PROMPT,
    "enforcer": ENFORCER_SYSTEM_PROMPT,
}


def run_stance_turn(
    client: instructor.Instructor,
    raw_client: Groq,
    stance: str,
    content: str,
    bundle: ContextBundle,
    prior_turns: list[DebateTurn],
    model: str = DEFAULT_MODEL,
) -> DebateTurn:
    system_prompt = STANCE_PROMPTS[stance]
    history = "\n".join(
        f"[{turn.stance}] position={turn.position} confidence={turn.confidence}: {turn.rationale}"
        for turn in prior_turns
    )

    user_message = (
        f"Content under review:\n{content}\n\n"
        f"Category: {bundle.category.value}\n"
        f"Severity: {bundle.policy.severity.value}\n"
        f"Rubric: {bundle.policy.rubric}\n\n"
        f"Prior debate turns:\n{history or '(none yet)'}"
    )

    tool_context = gather_tool_context(raw_client, model, system_prompt, user_message)
    if tool_context:
        user_message += f"\n\nTool lookups you made:\n{tool_context}"

    return client.chat.completions.create(
        model=model,
        response_model=DebateTurn,
        max_retries=MAX_RETRIES,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
