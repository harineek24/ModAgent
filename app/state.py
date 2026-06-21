import streamlit as st


def init_session_state() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []
    if "verdicts" not in st.session_state:
        st.session_state.verdicts = None


def record_run(content: str, verdicts) -> None:
    st.session_state.history.append({"content": content, "verdicts": verdicts})
    st.session_state.verdicts = verdicts
