import streamlit as st

from app.components.input_panel import render_input_panel
from app.components.verdict_panel import render_verdicts
from app.state import init_session_state, record_run
from backend.graph_runner import run

st.set_page_config(page_title="ModAgent", layout="wide")
st.title("ModAgent — Dynamic Parallel Debate Content Moderation")

init_session_state()

content, submitted = render_input_panel()

if submitted and content.strip():
    with st.spinner("Running classification + debate..."):
        verdicts = run(content)
    record_run(content, verdicts)

if st.session_state.verdicts is not None:
    render_verdicts(st.session_state.verdicts)
