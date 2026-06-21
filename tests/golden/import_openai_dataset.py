"""One-time/repeatable importer: turns the bundled OpenAI moderation eval
samples (tests/golden/raw/openai_moderation_samples.jsonl.gz, MIT licensed,
from openai/moderation-api-release) into tests/golden/moderation_cases.json.

Run with: python -m tests.golden.import_openai_dataset

Rows carrying the sexual/minors label are skipped entirely (not just excluded
from category mapping) -- this importer must never write real-world content
associated with that label into the golden set, even as a negative example
for another category. Hard-route categories (per the policy table's
`debatable` flag) are kept structurally separate from debatable ones so
golden cases assert against `expected_hard_routed` vs `expected_destinations`
correctly.
"""

import gzip
import json
import random
from pathlib import Path

from backend.routing.policy_loader import load_policy_table
from tests.golden.label_mapping import (
    DATASET_CODE_TO_OPENAI_LABEL,
    EXCLUDED_FROM_AUTO_IMPORT,
    OPENAI_TO_INTERNAL,
)

RAW_PATH = Path(__file__).parent / "raw" / "openai_moderation_samples.jsonl.gz"
OUTPUT_PATH = Path(__file__).parent / "moderation_cases.json"

RANDOM_SEED = 1337
MAX_PER_CATEGORY = 15
MAX_BENIGN = 15


def _load_raw_rows() -> list[dict]:
    with gzip.open(RAW_PATH, "rt") as f:
        return [json.loads(line) for line in f if line.strip()]


def _row_to_categories(row: dict) -> set | None:
    """Returns the set of internal categories flagged for this row, or None if
    the row must be skipped entirely (e.g. sexual/minors positive)."""
    openai_labels = {label for code, label in DATASET_CODE_TO_OPENAI_LABEL.items() if row.get(code) == 1}

    if openai_labels & EXCLUDED_FROM_AUTO_IMPORT:
        return None

    return {OPENAI_TO_INTERNAL[label] for label in openai_labels if label in OPENAI_TO_INTERNAL}


def build_golden_cases() -> list[dict]:
    policy_table = load_policy_table()
    rows = _load_raw_rows()

    positive_cases: list[dict] = []
    benign_cases: list[dict] = []

    for row in rows:
        categories = _row_to_categories(row)
        if categories is None:
            continue

        content = row["prompt"].strip()
        if not content:
            continue

        if not categories:
            benign_cases.append(
                {
                    "content": content,
                    "expected_destinations": [],
                    "expected_hard_routed": [],
                    "source": "openai-moderation-eval",
                }
            )
            continue

        destinations = sorted(c.value for c in categories if policy_table[c].debatable)
        hard_routed = sorted(c.value for c in categories if not policy_table[c].debatable)

        positive_cases.append(
            {
                "content": content,
                "expected_destinations": destinations,
                "expected_hard_routed": hard_routed,
                "source": "openai-moderation-eval",
            }
        )

    rng = random.Random(RANDOM_SEED)

    by_category_signature: dict[tuple, list[dict]] = {}
    for case in positive_cases:
        signature = (tuple(case["expected_destinations"]), tuple(case["expected_hard_routed"]))
        by_category_signature.setdefault(signature, []).append(case)

    sampled_positive: list[dict] = []
    for signature, cases in sorted(by_category_signature.items()):
        rng.shuffle(cases)
        sampled_positive.extend(cases[:MAX_PER_CATEGORY])

    rng.shuffle(benign_cases)
    sampled_benign = benign_cases[:MAX_BENIGN]

    hand_written = [
        {
            "content": "I think we should debate the merits of this policy proposal calmly.",
            "expected_destinations": [],
            "expected_hard_routed": [],
            "source": "hand-written",
        }
    ]

    return hand_written + sampled_positive + sampled_benign


def main() -> None:
    cases = build_golden_cases()
    OUTPUT_PATH.write_text(json.dumps(cases, indent=2) + "\n")
    print(f"Wrote {len(cases)} golden cases to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
