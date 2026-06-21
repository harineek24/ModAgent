"""Sweep AGREEMENT_CONFIDENCE_THRESHOLD / MAX_ROUNDS against a corpus of
*real* recorded debate transcripts to see how termination settings would
have behaved.

This is deliberately not wired into pytest/CI: it requires real Advocate/
Enforcer transcripts (i.e. live LLM debate runs), which the current golden
dataset does not contain (it only has router-level category labels, not
debate dynamics). Run it once you have a corpus of saved transcripts to
make threshold changes evidence-based instead of guessed.

Expected input file: a JSON list of records shaped like
    {
      "category": "hate_speech",
      "rounds": [
        {"advocate": {"position": "restrict", "confidence": 0.8},
         "enforcer": {"position": "restrict", "confidence": 0.7}},
        ...
      ],
      "expected_decision": "restrict"   # optional, for accuracy scoring
    }

Usage:
    python -m scripts.calibrate_termination path/to/transcripts.json
"""

import json
import sys
from itertools import product


def _agrees(round_, threshold: float) -> bool:
    a, e = round_["advocate"], round_["enforcer"]
    return a["position"] == e["position"] and a["confidence"] >= threshold and e["confidence"] >= threshold


def _simulate(record: dict, threshold: float, max_rounds: int) -> str:
    """Returns 'resolved' or 'escalated_unresolved' under the given settings."""
    rounds = record["rounds"][:max_rounds]
    for i, round_ in enumerate(rounds, start=1):
        if _agrees(round_, threshold):
            return "resolved"
        if i >= max_rounds:
            return "escalated_unresolved"
    return "escalated_unresolved"


def sweep(records: list[dict], thresholds: list[float], round_counts: list[int]) -> None:
    print(f"{len(records)} recorded transcripts\n")
    header = f"{'threshold':>10} {'max_rounds':>10} {'resolved':>10} {'escalated':>10} {'avg_rounds_used':>16}"
    print(header)
    print("-" * len(header))
    for threshold, max_rounds in product(thresholds, round_counts):
        outcomes = [_simulate(r, threshold, max_rounds) for r in records]
        resolved = sum(o == "resolved" for o in outcomes)
        escalated = len(outcomes) - resolved
        avg_rounds = sum(min(len(r["rounds"]), max_rounds) for r in records) / len(records)
        print(f"{threshold:>10.2f} {max_rounds:>10} {resolved:>10} {escalated:>10} {avg_rounds:>16.2f}")


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        records = json.load(f)

    sweep(records, thresholds=[0.7, 0.75, 0.8, 0.85, 0.9], round_counts=[1, 2, 3, 4])


if __name__ == "__main__":
    main()
