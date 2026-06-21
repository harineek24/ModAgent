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


def should_continue_debate(round_number: int, advocate_turn: DebateTurn, enforcer_turn: DebateTurn) -> bool:
    if round_number >= MAX_ROUNDS:
        return False
    return not turns_agree(advocate_turn, enforcer_turn)
