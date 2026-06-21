import streamlit as st

from app.components.debate_view import render_debate_turns
from backend.models.debate import ModerationResult

DECISION_COLOR = {"allow": "green", "restrict": "red", "escalate": "orange"}


def render_verdicts(result: ModerationResult) -> None:
    if not result.verdicts:
        st.success("No policy violations detected.")
        return

    for verdict in result.verdicts:
        color = DECISION_COLOR.get(verdict.decision, "gray")
        st.markdown(f"### {verdict.category.value} — :{color}[{verdict.decision.upper()}]")
        st.write(f"Confidence: {verdict.confidence:.2f}")
        st.write(verdict.rationale)
        if verdict.cited_clauses:
            with st.expander("Cited policy clauses"):
                for clause in verdict.cited_clauses:
                    st.write(f"- {clause}")
        if verdict.escalated:
            st.warning("Escalated to human review.")

        transcript = result.transcript_for(verdict.category)
        if transcript and (transcript.advocate_turns or transcript.enforcer_turns):
            with st.expander("Debate transcript"):
                render_debate_turns(transcript.advocate_turns, transcript.enforcer_turns)
