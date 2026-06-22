"""Tools available to debate tenants (Advocate, Enforcer, Judge) for grounding
their reasoning in the actual policy table instead of recalling rubric text
from the prompt alone. Implemented as plain local Python functions over the
already-loaded policy table -- no network calls -- and exposed to the model
via Groq's native function-calling so each tenant can call them only when it
actually needs to.
"""

import json

from groq import Groq

from backend.models.category import Category
from backend.routing.policy_loader import load_policy_table

MAX_TOOL_ROUNDS = 2

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "policy_lookup",
            "description": (
                "Look up the full policy entry for a moderation category: its severity tier, "
                "rubric text, and hand-written example cases. Use this to check precedent before "
                "deciding your position."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "The category value, e.g. 'hate_speech'."}
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clause_lookup",
            "description": (
                "Search a category's rubric and examples for text matching a query, to find the "
                "most precise clause to cite in your rationale instead of guessing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "query": {"type": "string", "description": "Keyword or phrase to search for."},
                },
                "required": ["category", "query"],
            },
        },
    },
]


def policy_lookup(category: str) -> dict:
    policy_table = load_policy_table()
    policy = policy_table[Category(category)]
    return {
        "severity": policy.severity.value,
        "rubric": policy.rubric,
        "examples": policy.examples,
        "debatable": policy.debatable,
    }


def clause_lookup(category: str, query: str) -> dict:
    policy_table = load_policy_table()
    policy = policy_table[Category(category)]
    query_lower = query.lower()
    matches = [ex for ex in policy.examples if query_lower in ex.lower()]
    if query_lower in policy.rubric.lower():
        matches.insert(0, policy.rubric)
    return {"matches": matches or [policy.rubric]}


TOOL_FUNCTIONS = {"policy_lookup": policy_lookup, "clause_lookup": clause_lookup}


def gather_tool_context(raw_client: Groq, model: str, system_prompt: str, user_message: str) -> str:
    """Lets the model optionally call policy_lookup/clause_lookup before the
    real structured-output call is made. Returns a plain-text summary of
    whatever it looked up (empty string if it used no tools), which gets
    appended to the user message of the actual DebateTurn/Verdict call.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": user_message
            + "\n\nIf you need to verify policy wording or example cases before answering, "
            "call a tool now. Otherwise respond with no tool calls.",
        },
    ]
    context_lines: list[str] = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = raw_client.chat.completions.create(
            model=model, messages=messages, tools=TOOL_SCHEMAS, tool_choice="auto"
        )
        message = response.choices[0].message
        tool_calls = getattr(message, "tool_calls", None)
        if not tool_calls:
            break

        messages.append(message)
        for call in tool_calls:
            args = json.loads(call.function.arguments)
            result = TOOL_FUNCTIONS[call.function.name](**args)
            context_lines.append(f"{call.function.name}({args}) -> {result}")
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    return "\n".join(context_lines)
