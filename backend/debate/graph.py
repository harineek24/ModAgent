"""LangGraph wiring: intake -> classify -> route -> fan-out (Send) per
destination -> per-category debate -> agreement check -> (resolve directly,
or judge) -> fan-in -> output.

This module wires nodes together; the actual decision logic lives in
classification/, routing/, and debate/superagents.py|agreement.py|judge.py
so each piece stays independently testable.

Each category's debate is a single shot: Advocate speaks once, Enforcer
speaks once, then an Agreement Check scores how much they substantively
agree (0-100), independent of exact wording. The expensive Judge call is
only made when that score is below threshold -- most categories resolve in
3 calls total instead of repeatedly round-tripping Advocate/Enforcer and
always calling a Judge.

There is no AI-triggered escalation path: every verdict is a final allow/
restrict decision the system stands behind, and every verdict (whatever the
decision) is surfaced to a human reviewer afterward regardless. Categories
that are too sensitive to leave to a debate at all (non-debatable, e.g.
CSAE) are still hard-routed straight to a "restrict" verdict with no debate
performed, since that's a pre-debate routing decision, not an AI escalation.
"""

from typing import Annotated, TypedDict
import operator

from langgraph.graph import END, StateGraph
from langgraph.types import Send

from backend.classification.classifier import classify
from backend.clients.groq_client import get_instructor_client, get_raw_client
from backend.debate.agreement import check_agreement, is_resolved
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
        decision="restrict",
        confidence=1.0,
        rationale=f"{bundle.category.value} is too sensitive to debate; restricted by policy with no debate performed.",
        cited_clauses=[bundle.policy.rubric],
    )
    return {"verdicts": [verdict]}


def debate_turn_node(state: DebateState) -> dict:
    client = get_instructor_client(state.get("api_key"))
    raw_client = get_raw_client(state.get("api_key"))
    bundle = state["bundle"]

    advocate_turn = run_stance_turn(client, raw_client, "advocate", state["content"], bundle, [])
    enforcer_turn = run_stance_turn(client, raw_client, "enforcer", state["content"], bundle, [])

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
    return "judge"


def resolve_node(state: DebateState) -> dict:
    bundle = state["bundle"]
    advocate_turn = state["advocate_turn"]
    enforcer_turn = state["enforcer_turn"]
    agreement = state["agreement"]

    verdict = Verdict(
        category=bundle.category,
        decision=agreement.resolved_position,
        confidence=min(advocate_turn.confidence, enforcer_turn.confidence) * (agreement.agreement_score / 100),
        rationale=agreement.rationale,
        cited_clauses=advocate_turn.cited_clauses + enforcer_turn.cited_clauses,
        agreement_score=agreement.agreement_score,
    )
    transcript = DebateTranscript(
        category=bundle.category, advocate_turns=[advocate_turn], enforcer_turns=[enforcer_turn]
    )
    return {"verdicts": [verdict], "transcripts": [transcript]}


def judge_node(state: DebateState) -> dict:
    client = get_instructor_client(state.get("api_key"))
    raw_client = get_raw_client(state.get("api_key"))
    advocate_turn = state["advocate_turn"]
    enforcer_turn = state["enforcer_turn"]
    verdict = reach_verdict(client, raw_client, state["content"], state["bundle"], advocate_turn, enforcer_turn)
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
    subgraph.add_node("judge", judge_node)

    subgraph.set_entry_point("debate_turn")
    subgraph.add_edge("debate_turn", "agreement_check")
    subgraph.add_conditional_edges("agreement_check", agreement_routing_edge, {
        "resolve": "resolve",
        "judge": "judge",
    })
    subgraph.add_edge("resolve", END)
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
