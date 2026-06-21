"""Superagent nodes: each is an LLM-boundary call producing one DebateTurn for a
given stance, scoped to a single category's ContextBundle.
"""

import instructor

from backend.clients.groq_client import DEFAULT_MODEL
from backend.debate.prompts import ADVOCATE_SYSTEM_PROMPT, ENFORCER_SYSTEM_PROMPT
from backend.models.debate import DebateTurn
from backend.models.routing import ContextBundle

STANCE_PROMPTS = {
    "advocate": ADVOCATE_SYSTEM_PROMPT,
    "enforcer": ENFORCER_SYSTEM_PROMPT,
}


def run_stance_turn(
    client: instructor.Instructor,
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

    return client.chat.completions.create(
        model=model,
        response_model=DebateTurn,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
