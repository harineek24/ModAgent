"""Pure logic deciding whether a debate round should continue, independent of
any LLM call -- kept separate so it's unit-testable on its own.
"""

from backend.models.debate import DebateTurn

MAX_ROUNDS = 3
AGREEMENT_CONFIDENCE_THRESHOLD = 0.85


def turns_agree(advocate_turn: DebateTurn, enforcer_turn: DebateTurn) -> bool:
    same_position = advocate_turn.position == enforcer_turn.position
    both_confident = (
        advocate_turn.confidence >= AGREEMENT_CONFIDENCE_THRESHOLD
        and enforcer_turn.confidence >= AGREEMENT_CONFIDENCE_THRESHOLD
    )
    return same_position and both_confident


def disagreement_reason(advocate_turn: DebateTurn, enforcer_turn: DebateTurn) -> str:
    """Diagnoses *why* turns_agree() failed, for surfacing to users instead of
    a single generic "disagreed" message. Only meaningful when turns_agree()
    is False.
    """
    if advocate_turn.position != enforcer_turn.position:
        return "position_mismatch"
    return "low_confidence"


def both_acknowledge_violation(advocate_turn: DebateTurn, enforcer_turn: DebateTurn) -> bool:
    """True when neither side thinks the content should be allowed -- i.e. the
    Advocate's free-expression mandate caps out at "restrict" while the
    Enforcer's caution mandate reaches "escalate", but both agree something is
    wrong. This is a disagreement about remedy severity, not about whether a
    violation occurred, and shouldn't be treated the same as a real tie
    (e.g. "allow" vs. "escalate") for fail-closed tie-breaking purposes.
    """
    return advocate_turn.position != "allow" and enforcer_turn.position != "allow"


def should_continue_debate(round_number: int, advocate_turn: DebateTurn, enforcer_turn: DebateTurn) -> bool:
    if round_number >= MAX_ROUNDS:
        return False
    return not turns_agree(advocate_turn, enforcer_turn)
