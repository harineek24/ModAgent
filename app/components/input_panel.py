import streamlit as st


def render_input_panel() -> tuple[str, bool]:
    content = st.text_area("Content to moderate", height=150)
    submitted = st.button("Run moderation")
    return content, submitted
