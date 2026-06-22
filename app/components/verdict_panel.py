import streamlit as st

from app.components.debate_view import render_debate_turns
from backend.models.debate import ModerationResult

DECISION_ICON = {"allow": "✅", "restrict": "⛔"}
DECISION_RANK = {"restrict": 0, "allow": 1}
GROUP_TITLE = {
    "restrict": "⛔ Restricted",
    "allow": "✅ Allowed",
}


def _overall_banner(result) -> None:
    decisions = {v.decision for v in result.verdicts}
    if "restrict" in decisions:
        st.error(f"**Overall: RESTRICTED** — {sum(v.decision == 'restrict' for v in result.verdicts)} "
                  f"of {len(result.verdicts)} flagged categories violate policy.")
    else:
        st.success("**Overall: ALLOWED** — flagged categories were resolved without restriction.")


def render_verdicts(result: ModerationResult) -> None:
    if not result.verdicts:
        st.success("No policy violations detected.")
        return

    _overall_banner(result)
    st.caption("Every result below — whatever the decision — is provided for human review.")

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
    for decision in ("restrict", "allow"):
        group = [v for v in ordered if v.decision == decision]
        if not group:
            continue
        st.markdown(f"#### {GROUP_TITLE[decision]}")
        for verdict in group:
            icon = DECISION_ICON.get(verdict.decision, "•")
            with st.expander(f"{icon} {verdict.category.value} (conf. {verdict.confidence:.2f})"):
                transcript = result.transcript_for(verdict.category)

                if verdict.agreement_score is not None:
                    st.caption(f"Advocate/Enforcer agreement: {verdict.agreement_score}/100")
                st.write(verdict.rationale)

                unique_clauses = list(dict.fromkeys(verdict.cited_clauses))
                if unique_clauses:
                    st.markdown("**Cited policy clauses**")
                    for clause in unique_clauses:
                        st.write(f"- {clause}")

                if transcript and (transcript.advocate_turns or transcript.enforcer_turns):
                    st.markdown("**Debate transcript**")
                    render_debate_turns(transcript.advocate_turns, transcript.enforcer_turns)
                else:
                    st.info("No debate was held — this category is too sensitive to debate by policy.")
