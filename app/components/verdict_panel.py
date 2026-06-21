import streamlit as st

from app.components.debate_view import render_debate_turns
from backend.models.debate import ModerationResult

DECISION_ICON = {"allow": "✅", "restrict": "⛔", "escalate": "🟠"}
DECISION_RANK = {"escalate": 0, "restrict": 1, "allow": 2}
GROUP_TITLE = {
    "escalate": "🟠 Needs human review",
    "restrict": "⛔ Restricted",
    "allow": "✅ Allowed",
}


def _overall_banner(result) -> None:
    decisions = {v.decision for v in result.verdicts}
    if "escalate" in decisions:
        st.warning(f"**Overall: NEEDS HUMAN REVIEW** — {sum(v.decision == 'escalate' for v in result.verdicts)} "
                    f"of {len(result.verdicts)} flagged categories require escalation.")
    elif "restrict" in decisions:
        st.error(f"**Overall: RESTRICTED** — {sum(v.decision == 'restrict' for v in result.verdicts)} "
                  f"of {len(result.verdicts)} flagged categories violate policy.")
    else:
        st.success("**Overall: ALLOWED** — flagged categories were resolved without restriction.")


def render_verdicts(result: ModerationResult) -> None:
    if not result.verdicts:
        st.success("No policy violations detected.")
        return

    _overall_banner(result)

    st.subheader("Summary")
    ordered = sorted(result.verdicts, key=lambda v: DECISION_RANK.get(v.decision, 99))
    st.table(
        [
            {
                "Category": v.category.value,
                "Decision": f"{DECISION_ICON.get(v.decision, '•')} {v.decision.upper()}",
                "Confidence": f"{v.confidence:.2f}",
            }
            for v in ordered
        ]
    )

    st.subheader("Details")
    for decision in ("escalate", "restrict", "allow"):
        group = [v for v in ordered if v.decision == decision]
        if not group:
            continue
        st.markdown(f"#### {GROUP_TITLE[decision]}")
        for verdict in group:
            icon = DECISION_ICON.get(verdict.decision, "•")
            with st.expander(f"{icon} {verdict.category.value} (conf. {verdict.confidence:.2f})"):
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
