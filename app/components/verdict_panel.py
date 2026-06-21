import streamlit as st

from app.components.debate_view import render_debate_turns
from backend.models.debate import ModerationResult

DECISION_ICON = {"allow": "✅", "restrict": "⛔", "escalate": "🟠"}


def render_verdicts(result: ModerationResult) -> None:
    if not result.verdicts:
        st.success("No policy violations detected.")
        return

    st.subheader("Summary")
    st.table(
        [
            {
                "Category": v.category.value,
                "Decision": f"{DECISION_ICON.get(v.decision, '•')} {v.decision.upper()}",
                "Confidence": f"{v.confidence:.2f}",
                "Escalated": "Yes" if v.escalated else "No",
            }
            for v in result.verdicts
        ]
    )

    st.subheader("Details")
    for verdict in result.verdicts:
        icon = DECISION_ICON.get(verdict.decision, "•")
        with st.expander(f"{icon} {verdict.category.value} — {verdict.decision.upper()} (conf. {verdict.confidence:.2f})"):
            if verdict.escalated:
                st.warning("Escalated to human review.")
            st.write(verdict.rationale)

            unique_clauses = list(dict.fromkeys(verdict.cited_clauses))
            if unique_clauses:
                st.markdown("**Cited policy clauses**")
                for clause in unique_clauses:
                    st.write(f"- {clause}")

            transcript = result.transcript_for(verdict.category)
            if transcript and (transcript.advocate_turns or transcript.enforcer_turns):
                st.markdown("**Debate transcript**")
                render_debate_turns(transcript.advocate_turns, transcript.enforcer_turns)
            elif verdict.escalated and "disagreed" in verdict.rationale.lower():
                st.info("Debate transcript unavailable for this verdict.")
