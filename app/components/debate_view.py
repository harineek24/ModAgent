import streamlit as st

from backend.models.debate import DebateTurn


def render_debate_turns(advocate_turns: list[DebateTurn], enforcer_turns: list[DebateTurn]) -> None:
    rounds = max(len(advocate_turns), len(enforcer_turns))
    for i in range(rounds):
        st.markdown(f"**Round {i + 1}**")
        left, right = st.columns(2)
        if i < len(advocate_turns):
            turn = advocate_turns[i]
            left.markdown(f"**Advocate** — {turn.position} ({turn.confidence:.2f})")
            left.write(turn.rationale)
        if i < len(enforcer_turns):
            turn = enforcer_turns[i]
            right.markdown(f"**Enforcer** — {turn.position} ({turn.confidence:.2f})")
            right.write(turn.rationale)
