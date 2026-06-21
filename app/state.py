import streamlit as st

from backend.models.debate import ModerationResult


def init_session_state() -> None:
    if "result" not in st.session_state:
        st.session_state.result = None


def record_run(result: ModerationResult) -> None:
    st.session_state.result = result
