"""LangGraph wiring: intake -> classify -> route -> fan-out (Send) per
destination -> per-category debate -> agreement check -> (resolve directly,
fail-closed escalate, or judge) -> fan-in -> output.

This module wires nodes together; the actual decision logic lives in
classification/, routing/, and debate/superagents.py|agreement.py|judge.py
so each piece stays independently testable.

Each category's debate is now a single shot: Advocate speaks once, Enforcer
speaks once, then an Agreement Check scores how much they substantively
agree (0-100), independent of exact wording. The expensive Judge call is
only made when that score is below threshold *and* the category doesn't
fail closed on ties by policy -- most categories resolve in 3 calls total
instead of repeatedly round-tripping Advocate/Enforcer and always calling a
Judge.
"""

from typing import Annotated, TypedDict
import operator

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from backend.classification.classifier import classify
from backend.clients.groq_client import get_instructor_client
from backend.debate.agreement import AGREEMENT_THRESHOLD, check_agreement, is_resolved
from backend.debate.judge import reach_verdict
from backend.debate.superagents import run_stance_turn
from backend.models.debate import AgreementCheck, DebateTranscript, DebateTurn, Verdict
from backend.models.routing import ContextBundle
from backend.routing.policy_loader import load_policy_table
from backend.routing.router import route


class GraphState(TypedDict):
    content: str
    api_key: str | None
    classification_scores: dict
    destinations: list[ContextBundle]
    hard_routed: list[ContextBundle]
    verdicts: Annotated[list[Verdict], operator.add]
    transcripts: Annotated[list[DebateTranscript], operator.add]


class DebateState(TypedDict):
    content: str
    api_key: str | None
    bundle: ContextBundle
    advocate_turn: DebateTurn
    enforcer_turn: DebateTurn
    agreement: AgreementCheck
    verdicts: Annotated[list[Verdict], operator.add]
    transcripts: Annotated[list[DebateTranscript], operator.add]


def intake_and_classify_node(state: GraphState) -> dict:
    client = get_instructor_client(state.get("api_key"))
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
    sends = [
        Send("debate_subgraph", {"content": state["content"], "api_key": state.get("api_key"), "bundle": bundle})
        for bundle in state["destinations"]
    ]
    sends += [
        Send("hard_route_verdict", {"content": state["content"], "bundle": bundle})
        for bundle in state["hard_routed"]
    ]
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
        escalation_reason="non_debatable",
    )
    return {"verdicts": [verdict]}


def debate_turn_node(state: DebateState) -> dict:
    client = get_instructor_client(state.get("api_key"))
    bundle = state["bundle"]

    advocate_turn = run_stance_turn(client, "advocate", state["content"], bundle, [])
    enforcer_turn = run_stance_turn(client, "enforcer", state["content"], bundle, [])

    return {"advocate_turn": advocate_turn, "enforcer_turn": enforcer_turn}


def agreement_check_node(state: DebateState) -> dict:
    client = get_instructor_client(state.get("api_key"))
    agreement = check_agreement(
        client, state["content"], state["bundle"], state["advocate_turn"], state["enforcer_turn"]
    )
    return {"agreement": agreement}


def agreement_routing_edge(state: DebateState) -> str:
    if is_resolved(state["agreement"]):
        return "resolve"
    if state["bundle"].policy.escalate_on_tie:
        return "fail_closed_escalate"
    return "judge"


def resolve_node(state: DebateState) -> dict:
    bundle = state["bundle"]
    advocate_turn = state["advocate_turn"]
    enforcer_turn = state["enforcer_turn"]
    agreement = state["agreement"]
    position = agreement.resolved_position

    verdict = Verdict(
        category=bundle.category,
        decision=position,
        confidence=min(advocate_turn.confidence, enforcer_turn.confidence) * (agreement.agreement_score / 100),
        rationale=agreement.rationale,
        cited_clauses=advocate_turn.cited_clauses + enforcer_turn.cited_clauses,
        escalated=position == "escalate",
        escalation_reason="agreement_escalated" if position == "escalate" else None,
        agreement_score=agreement.agreement_score,
    )
    transcript = DebateTranscript(
        category=bundle.category, advocate_turns=[advocate_turn], enforcer_turns=[enforcer_turn]
    )
    return {"verdicts": [verdict], "transcripts": [transcript]}


def fail_closed_escalate_node(state: DebateState) -> dict:
    bundle = state["bundle"]
    advocate_turn = state["advocate_turn"]
    enforcer_turn = state["enforcer_turn"]
    agreement = state["agreement"]

    verdict = Verdict(
        category=bundle.category,
        decision="escalate",
        confidence=min(advocate_turn.confidence, enforcer_turn.confidence),
        rationale=(
            f"Advocate and Enforcer only scored {agreement.agreement_score}/100 on agreement "
            f"(below the {AGREEMENT_THRESHOLD} threshold); this category fails closed on "
            "unresolved disagreement rather than risking an automatic allow."
        ),
        cited_clauses=advocate_turn.cited_clauses + enforcer_turn.cited_clauses,
        escalated=True,
        escalation_reason="low_agreement",
        agreement_score=agreement.agreement_score,
    )
    transcript = DebateTranscript(
        category=bundle.category, advocate_turns=[advocate_turn], enforcer_turns=[enforcer_turn]
    )
    return {"verdicts": [verdict], "transcripts": [transcript]}


def judge_node(state: DebateState) -> dict:
    client = get_instructor_client(state.get("api_key"))
    advocate_turn = state["advocate_turn"]
    enforcer_turn = state["enforcer_turn"]
    verdict = reach_verdict(client, state["content"], state["bundle"], advocate_turn, enforcer_turn)
    verdict = verdict.model_copy(update={"agreement_score": state["agreement"].agreement_score})
    transcript = DebateTranscript(
        category=state["bundle"].category, advocate_turns=[advocate_turn], enforcer_turns=[enforcer_turn]
    )
    return {"verdicts": [verdict], "transcripts": [transcript]}


def build_debate_subgraph() -> StateGraph:
    subgraph = StateGraph(DebateState)
    subgraph.add_node("debate_turn", debate_turn_node)
    subgraph.add_node("agreement_check", agreement_check_node)
    subgraph.add_node("resolve", resolve_node)
    subgraph.add_node("fail_closed_escalate", fail_closed_escalate_node)
    subgraph.add_node("judge", judge_node)

    subgraph.set_entry_point("debate_turn")
    subgraph.add_edge("debate_turn", "agreement_check")
    subgraph.add_conditional_edges("agreement_check", agreement_routing_edge, {
        "resolve": "resolve",
        "fail_closed_escalate": "fail_closed_escalate",
        "judge": "judge",
    })
    subgraph.add_edge("resolve", END)
    subgraph.add_edge("fail_closed_escalate", END)
    subgraph.add_edge("judge", END)
    return subgraph


def make_debate_subgraph_node(compiled_subgraph):
    """Wraps the compiled debate subgraph so only the fan-in keys
    (verdicts, transcripts) propagate to the parent graph. Parallel
    Send branches share the parent's content/api_key channels, which
    are plain last-value channels; returning those fields from every
    branch causes an INVALID_CONCURRENT_GRAPH_UPDATE error.
    """

    def _run(state: DebateState) -> dict:
        result = compiled_subgraph.invoke(state)
        return {"verdicts": result["verdicts"], "transcripts": result["transcripts"]}

    return _run


def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)
    graph.add_node("intake_and_classify", intake_and_classify_node)
    graph.add_node("route", route_node)
    graph.add_node("debate_subgraph", make_debate_subgraph_node(build_debate_subgraph().compile()))
    graph.add_node("hard_route_verdict", hard_route_verdict_node)

    graph.set_entry_point("intake_and_classify")
    graph.add_edge("intake_and_classify", "route")
    graph.add_conditional_edges("route", dispatch_to_debates, ["debate_subgraph", "hard_route_verdict"])
    graph.add_edge("debate_subgraph", END)
    graph.add_edge("hard_route_verdict", END)

    return graph
