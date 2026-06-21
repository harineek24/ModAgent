"""Pure routing logic: ClassificationResult -> RouterOutput.

No network calls, no LLM clients. This module must stay deterministic and
side-effect free so it can be unit-tested without mocking anything.
"""

from backend.models.category import Category
from backend.models.classification import ClassificationResult
from backend.models.policy import CategoryPolicy
from backend.models.routing import ContextBundle, RouterOutput

DEFAULT_THRESHOLD = 0.5


def route(
    classification: ClassificationResult,
    policy_table: dict[Category, CategoryPolicy],
    threshold: float = DEFAULT_THRESHOLD,
) -> RouterOutput:
    destinations: list[ContextBundle] = []
    hard_routed: list[ContextBundle] = []

    for category, score in classification.scores.items():
        if category == Category.BENIGN:
            continue
        if score < threshold:
            continue

        policy = policy_table[category]
        bundle = ContextBundle(category=category, policy=policy, score=score)

        if policy.debatable:
            destinations.append(bundle)
        else:
            hard_routed.append(bundle)

    is_benign = not destinations and not hard_routed

    return RouterOutput(
        destinations=destinations,
        hard_routed=hard_routed,
        is_benign=is_benign,
    )
