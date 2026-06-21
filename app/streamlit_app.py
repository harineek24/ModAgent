import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.components.input_panel import render_input_panel
from app.components.verdict_panel import render_verdicts
from app.state import init_session_state, record_run
from backend.graph_runner import run

st.set_page_config(page_title="ModAgent", layout="wide")
st.title("ModAgent — Dynamic Parallel Debate Content Moderation")

init_session_state()

with st.sidebar:
    st.text_input(
        "Groq API key",
        type="password",
        key="groq_api_key",
        help="Used only for this session, kept in browser session state, never written to disk.",
    )

content, submitted = render_input_panel()

if submitted and not st.session_state.groq_api_key:
    st.error("Enter a Groq API key in the sidebar first.")
elif submitted and content.strip():
    with st.spinner("Running classification + debate..."):
        result = run(content, api_key=st.session_state.groq_api_key)
    record_run(result)

if st.session_state.result is not None:
    render_verdicts(st.session_state.result)
