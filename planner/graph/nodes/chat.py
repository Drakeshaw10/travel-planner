"""The conversation nodes: greet, wait_for_user and chat.

A LangGraph node is a function `state -> dict`. The dict holds only the keys the
node changes; LangGraph merges it into the state and saves a checkpoint.
"""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt

from planner.llm import MAX_HISTORY

GREETING = (
    "Hi! Let's find you a trip without you having to pick a place first. "
    "To start: right now, would you rather hear waves or birdsong?"
)

SYSTEM_PROMPT = (
    "You are a warm, curious travel companion for people in India who don't know "
    "where they want to go. Ask one short, friendly question at a time about their "
    "mood and preferences. Do not suggest destinations yet."
)


def greet(state) -> dict:
    """First node of every trip. A fixed message, so opening a trip costs no LLM call."""
    return {"messages": [AIMessage(GREETING)], "phase": "discovery"}


def wait_for_user(state) -> dict:
    """Pause the graph until the user replies, then add their reply to the history.

    How `interrupt()` works, because it is the core of human-in-the-loop:
    1. The first time this node runs, `interrupt()` raises a special signal.
       LangGraph stops the run and saves a checkpoint that says "paused here".
       The Streamlit script finishes; nothing is kept in memory.
    2. When the user types, app.py calls the graph with `Command(resume=text)`.
       LangGraph loads the checkpoint and runs this node again *from its first
       line*. This time `interrupt()` returns `text` instead of pausing.

    Because the node re-runs from the top, nothing before `interrupt()` may have
    side effects (no API calls, no database writes): they would happen twice.
    """
    text = interrupt("waiting_for_user")
    if not isinstance(text, str) or not text.strip():
        # Resume values come from outside the graph, so check them like any
        # user input instead of trusting them.
        raise ValueError("wait_for_user must be resumed with non-empty text")
    return {
        "messages": [HumanMessage(text.strip())],
        "user_turns": state.get("user_turns", 0) + 1,
    }


def make_chat(llm: BaseChatModel):
    """Build the `chat` node around a given model.

    Why a factory instead of calling `get_llm()` inside the node: the node gets
    its model passed in (dependency injection). Production passes the Hugging
    Face model; tests pass a fake one. The node never knows the difference, and
    the graph package never touches secrets.
    """

    def chat(state) -> dict:
        # Send only the most recent messages, to bound cost and latency.
        history = [SystemMessage(SYSTEM_PROMPT), *state["messages"][-MAX_HISTORY:]]
        # `invoke`, not `stream`: when app.py runs the graph with
        # stream_mode="messages", LangGraph hooks into this call and forwards
        # each token to the UI as it arrives. The node itself still gets back
        # one complete AIMessage to store in state.
        reply = llm.invoke(history)
        return {"messages": [reply]}

    return chat
