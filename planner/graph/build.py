"""Assemble the nodes and edges into a runnable, checkpointed graph.

Why a function that takes the model and checkpointer as arguments: the same
graph code runs in production (Gemini + Postgres) and in tests (fake model +
in-memory saver). Nothing in here reads secrets or opens connections.
"""

from collections.abc import Callable
from datetime import date

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph

from planner.graph.nodes.chat import greet, make_chat, wait_for_user
from planner.graph.nodes.constraints import make_constraints
from planner.graph.nodes.orchestrator import after_constraints, route
from planner.graph.nodes.profiler import make_profiler
from planner.graph.state import TravelState

# Only these nodes produce text meant for the user. app.py shows streamed tokens
# from these nodes and ignores LLM calls made by any other node. The profiler
# and constraints nodes make LLM calls too, but they return JSON, not prose.
STREAMING_NODES = frozenset({"chat", "writer"})

# Routing functions already know the full design from LLD.md. These maps turn
# their answers into nodes that exist *today*; each later phase changes one
# entry when it adds the real node, without touching the routing functions.
ROUTE_MAP = {
    "profiler": "profiler",
    "constraints": "constraints",
    "chat": "chat",
}
AFTER_CONSTRAINTS_MAP = {
    "scorer": "chat",  # later phase: "scorer"
    "chat": "chat",
}


def build_graph(
    llm: BaseChatModel,
    checkpointer: BaseCheckpointSaver,
    *,
    today: Callable[[], date] = date.today,
):
    """Compile the graph.

    `today` is handed to the constraints node so tests can fix the date; the
    `*` makes it keyword-only, so a call can never pass it by position by mistake.
    """
    g = StateGraph(TravelState)

    g.add_node("greet", greet)
    g.add_node("wait_for_user", wait_for_user)
    g.add_node("profiler", make_profiler(llm))
    g.add_node("constraints", make_constraints(llm, today=today))
    g.add_node("chat", make_chat(llm))

    # START -> greet -> wait_for_user -(route)-> profiler | constraints | chat
    # profiler -> chat;  constraints -(after_constraints)-> chat (later: scorer)
    # chat -> wait_for_user. Every run stops at the interrupt in wait_for_user.
    g.add_edge(START, "greet")
    g.add_edge("greet", "wait_for_user")
    g.add_conditional_edges("wait_for_user", route, ROUTE_MAP)
    g.add_edge("profiler", "chat")
    g.add_conditional_edges("constraints", after_constraints, AFTER_CONSTRAINTS_MAP)
    g.add_edge("chat", "wait_for_user")

    # Compiling with a checkpointer is what makes the graph durable: state is
    # saved after every node, keyed by the `thread_id` in the run config.
    return g.compile(checkpointer=checkpointer)
