from pathlib import Path

import yaml

from backend.exceptions import RouterConfigError
from backend.models.category import Category, SeverityTier
from backend.models.policy import CategoryPolicy

DEFAULT_POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "policy_table.yaml"


def load_policy_table(path: Path = DEFAULT_POLICY_PATH) -> dict[Category, CategoryPolicy]:
    raw = yaml.safe_load(path.read_text())

    policies: dict[Category, CategoryPolicy] = {}
    for key, row in raw.items():
        category = Category(key)
        policies[category] = CategoryPolicy(
            category=category,
            severity=SeverityTier(row["severity"]),
            debatable=row["debatable"],
            escalate_on_tie=row.get("escalate_on_tie", True),
            rubric=row["rubric"].strip(),
            examples=row.get("examples", []),
        )

    missing = set(Category) - set(policies)
    if missing:
        raise RouterConfigError(f"Policy table missing entries for: {missing}")

    for category, policy in policies.items():
        if policy.severity == SeverityTier.CRITICAL and policy.debatable:
            raise RouterConfigError(
                f"{category} has severity=critical but debatable=True; "
                "critical categories must be hard-routed."
            )

    return policies
