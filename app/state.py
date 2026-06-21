import streamlit as st

from backend.models.debate import ModerationResult


def init_session_state() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []
    if "result" not in st.session_state:
        st.session_state.result = None


def record_run(content: str, result: ModerationResult) -> None:
    st.session_state.history.append({"content": content, "result": result})
    st.session_state.result = result
