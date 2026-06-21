"""Public entry point for running the full moderation graph headlessly --
used by both the Streamlit app and tests/CLI/batch eval without any UI coupling.
"""

from backend.debate.graph import build_graph
from backend.models.debate import ModerationResult

_compiled_graph = None


def _get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


def run(content: str) -> ModerationResult:
    graph = _get_compiled_graph()
    final_state = graph.invoke({"content": content, "verdicts": [], "transcripts": []})
    return ModerationResult(
        verdicts=final_state["verdicts"],
        transcripts=final_state["transcripts"],
    )
