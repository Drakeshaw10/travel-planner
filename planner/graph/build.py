"""Assemble the nodes and edges into a runnable, checkpointed graph.

Why a function that takes the model and checkpointer as arguments: the same
graph code runs in production (Hugging Face model + Postgres) and in tests (fake
model + in-memory saver). Nothing in here reads secrets or opens connections.
"""

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import START, StateGraph

from planner.graph.nodes.chat import greet, make_chat, wait_for_user
from planner.graph.nodes.orchestrator import route
from planner.graph.state import TravelState

# Only these nodes produce text meant for the user. app.py shows streamed tokens
# from these nodes and ignores LLM calls made by any other node (for example the
# profiler's structured-output call, which returns JSON, not prose).
STREAMING_NODES = frozenset({"chat", "writer"})

# Phase 2 builds the conversation loop only. `route()` already knows the full
# design, so its answers for agents that don't exist yet are mapped to `chat`
# here. Each later phase adds its node and points its entry at it, e.g.
# "profiler": "profiler", without touching `route()` itself.
ROUTE_MAP = {
    "profiler": "chat",      # later phase: "profiler"
    "constraints": "chat",   # later phase: "constraints"
    "chat": "chat",
}


def build_graph(llm: BaseChatModel, checkpointer: BaseCheckpointSaver):
    g = StateGraph(TravelState)

    g.add_node("greet", greet)
    g.add_node("wait_for_user", wait_for_user)
    g.add_node("chat", make_chat(llm))

    # START -> greet -> wait_for_user -> (route) -> chat -> wait_for_user -> ...
    # The loop never reaches END: every run stops at the interrupt in
    # wait_for_user, and the checkpointer remembers where.
    g.add_edge(START, "greet")
    g.add_edge("greet", "wait_for_user")
    g.add_conditional_edges("wait_for_user", route, ROUTE_MAP)
    g.add_edge("chat", "wait_for_user")

    # Compiling with a checkpointer is what makes the graph durable: state is
    # saved after every node, keyed by the `thread_id` in the run config.
    return g.compile(checkpointer=checkpointer)
