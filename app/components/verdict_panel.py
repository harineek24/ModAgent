import streamlit as st

from backend.models.debate import Verdict

DECISION_COLOR = {"allow": "green", "restrict": "red", "escalate": "orange"}


def render_verdicts(verdicts: list[Verdict]) -> None:
    if not verdicts:
        st.success("No policy violations detected.")
        return

    for verdict in verdicts:
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
