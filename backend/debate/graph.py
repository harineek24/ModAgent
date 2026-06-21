"""LangGraph wiring: intake -> classify -> route -> fan-out (Send) per
destination -> per-category debate loop -> judge -> fan-in -> output.

This module wires nodes together; the actual decision logic lives in
classification/, routing/, and debate/superagents.py|judge.py|termination.py
so each piece stays independently testable.
"""

from typing import Annotated, TypedDict
import operator

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from backend.classification.classifier import classify
from backend.clients.groq_client import get_instructor_client
from backend.debate.judge import reach_verdict
from backend.debate.superagents import run_stance_turn
from backend.debate.termination import should_continue_debate
from backend.models.debate import DebateTurn, Verdict
from backend.models.routing import ContextBundle
from backend.routing.policy_loader import load_policy_table
from backend.routing.router import route


class GraphState(TypedDict):
    content: str
    classification_scores: dict
    destinations: list[ContextBundle]
    hard_routed: list[ContextBundle]
    verdicts: Annotated[list[Verdict], operator.add]


class DebateState(TypedDict):
    content: str
    bundle: ContextBundle
    round_number: int
    advocate_turns: list[DebateTurn]
    enforcer_turns: list[DebateTurn]
    verdicts: Annotated[list[Verdict], operator.add]


def intake_and_classify_node(state: GraphState) -> dict:
    client = get_instructor_client()
    result = classify(client, state["content"])
    return {"classification_scores": result}


def route_node(state: GraphState) -> dict:
    policy_table = load_policy_table()
    router_output = route(state["classification_scores"], policy_table)
    return {
        "destinations": router_output.destinations,
        "hard_routed": router_output.hard_routed,
    }


def dispatch_to_debates(state: GraphState):
    sends = [Send("debate_subgraph", {"content": state["content"], "bundle": bundle})
             for bundle in state["destinations"]]
    sends += [Send("hard_route_verdict", {"content": state["content"], "bundle": bundle})
              for bundle in state["hard_routed"]]
    return sends


def hard_route_verdict_node(state: dict) -> dict:
    bundle: ContextBundle = state["bundle"]
    verdict = Verdict(
        category=bundle.category,
        decision="escalate",
        confidence=1.0,
        rationale=f"{bundle.category.value} is hard-routed; no debate performed.",
        cited_clauses=[bundle.policy.rubric],
        escalated=True,
    )
    return {"verdicts": [verdict]}


def debate_round_node(state: DebateState) -> dict:
    client = get_instructor_client()
    bundle = state["bundle"]
    round_number = state.get("round_number", 0) + 1

    advocate_turn = run_stance_turn(
        client, "advocate", state["content"], bundle, state.get("advocate_turns", [])
    )
    enforcer_turn = run_stance_turn(
        client, "enforcer", state["content"], bundle, state.get("enforcer_turns", [])
    )

    return {
        "round_number": round_number,
        "advocate_turns": state.get("advocate_turns", []) + [advocate_turn],
        "enforcer_turns": state.get("enforcer_turns", []) + [enforcer_turn],
    }


def debate_continue_edge(state: DebateState) -> str:
    advocate_turn = state["advocate_turns"][-1]
    enforcer_turn = state["enforcer_turns"][-1]
    if should_continue_debate(state["round_number"], advocate_turn, enforcer_turn):
        return "debate_round"
    return "judge"


def judge_node(state: DebateState) -> dict:
    client = get_instructor_client()
    verdict = reach_verdict(
        client,
        state["content"],
        state["bundle"],
        state["advocate_turns"][-1],
        state["enforcer_turns"][-1],
    )
    return {"verdicts": [verdict]}


def build_debate_subgraph() -> StateGraph:
    subgraph = StateGraph(DebateState)
    subgraph.add_node("debate_round", debate_round_node)
    subgraph.add_node("judge", judge_node)
    subgraph.set_entry_point("debate_round")
    subgraph.add_conditional_edges("debate_round", debate_continue_edge, {
        "debate_round": "debate_round",
        "judge": "judge",
    })
    subgraph.add_edge("judge", END)
    return subgraph


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("intake_and_classify", intake_and_classify_node)
    graph.add_node("route", route_node)
    graph.add_node("debate_subgraph", build_debate_subgraph().compile())
    graph.add_node("hard_route_verdict", hard_route_verdict_node)

    graph.set_entry_point("intake_and_classify")
    graph.add_edge("intake_and_classify", "route")
    graph.add_conditional_edges("route", dispatch_to_debates, ["debate_subgraph", "hard_route_verdict"])
    graph.add_edge("debate_subgraph", END)
    graph.add_edge("hard_route_verdict", END)

    return graph
