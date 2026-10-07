"""Moody Trip Planner: the chat UI.

How a Streamlit app runs: the whole script re-runs top to bottom on every
click or message. So this file keeps no conversation in memory. Every rerun it
asks the graph for the saved state of this trip, draws it, and, if the user
typed something, resumes the graph with that text.
"""

import logging
import uuid

import streamlit as st
from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.types import Command

from planner.db import get_checkpointer
from planner.graph.build import STREAMING_NODES, build_graph
from planner.llm import get_llm

# Errors are logged in full for the developer (Streamlit Cloud shows these in
# "Manage app" -> logs) and shown to the user as a short, friendly message.
# Raw exception text can leak internals such as hostnames or request ids.
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Moody Trip Planner", page_icon="🧭")


@st.cache_resource
def get_graph():
    """Compile the graph once per server process; every session shares it.

    Sharing is safe because the compiled graph holds no per-user data. Each
    trip's state is stored in Postgres under its own thread_id.
    """
    return build_graph(get_llm(), get_checkpointer())


def current_trip_id() -> str:
    """Read the trip id from `?trip=` in the URL, or start a new trip.

    Why the URL and not st.session_state: session state dies when the tab
    closes or the app sleeps. A URL can be bookmarked or shared, and with the
    state in Postgres it reopens the exact conversation.

    The id is user input (anyone can edit a URL), so only a valid UUID is
    accepted. Random UUIDs are also unguessable, which is what keeps one
    person's trip private to whoever has the link.
    """
    try:
        return str(uuid.UUID(st.query_params.get("trip", "")))
    except ValueError:
        trip_id = str(uuid.uuid4())
        st.query_params["trip"] = trip_id
        return trip_id


def stream_reply(graph, payload, config):
    """Run the graph and yield only the text tokens meant for the user.

    stream_mode="messages" yields (token, metadata) for every LLM call in every
    node. metadata["langgraph_node"] says which node made the call, so only
    STREAMING_NODES reach the screen.
    """
    for chunk, metadata in graph.stream(payload, config, stream_mode="messages"):
        if (
            metadata.get("langgraph_node") in STREAMING_NODES
            and isinstance(chunk, AIMessageChunk)
            and isinstance(chunk.content, str)
            and chunk.content
        ):
            yield chunk.content


def run_turn(graph, payload, config):
    """Stream one graph run into an assistant bubble; on failure, offer Retry.

    If a node fails, the exception ends the run but the last checkpoint is
    already saved. The rerun below then finds the trip stopped mid-run and
    shows the Retry button, which resumes from that checkpoint.
    """
    with st.chat_message("assistant"):
        try:
            st.write_stream(stream_reply(graph, payload, config))
        except Exception:
            logger.exception("Graph run failed for %s", config["configurable"]["thread_id"])
            st.session_state.last_error = "Something went wrong while I was replying."
            st.rerun()


st.title("Moody Trip Planner")
st.caption("Not sure where to go? Let's figure it out together.")

trip_id = current_trip_id()
# thread_id tells the checkpointer which trip's state to load and save.
config = {"configurable": {"thread_id": trip_id}}

with st.sidebar:
    if st.button("New trip"):
        st.query_params["trip"] = str(uuid.uuid4())
        st.session_state.pop("last_error", None)
        st.rerun()
    st.caption("Bookmark this page to come back to this trip later.")

try:
    graph = get_graph()
    snapshot = graph.get_state(config)
    if not snapshot.values:
        # A brand-new trip: run greet, which stops at the first interrupt.
        graph.invoke({"messages": []}, config)
        snapshot = graph.get_state(config)
except Exception:
    logger.exception("Could not load trip %s", trip_id)
    st.error("I can't reach the trip database right now. Please refresh in a minute.")
    st.stop()

for msg in snapshot.values.get("messages", []):
    with st.chat_message("user" if isinstance(msg, HumanMessage) else "assistant"):
        st.markdown(msg.content)

# Three possible situations after drawing the history:
# - snapshot.interrupts is set: the graph is paused at wait_for_user and
#   expects the user's next message.
# - snapshot.next is set but there is no interrupt: a run stopped part-way
#   (a node raised). Typing now would have nothing to resume, so offer Retry.
# - neither: nothing to do (cannot happen in Phase 2, the loop never ends).
if snapshot.interrupts:
    if prompt := st.chat_input("Type your answer..."):
        st.session_state.pop("last_error", None)
        with st.chat_message("user"):
            st.markdown(prompt)
        # Command(resume=...) becomes the return value of interrupt() inside
        # wait_for_user, and the graph carries on from there.
        run_turn(graph, Command(resume=prompt), config)
elif snapshot.next:
    st.error(st.session_state.get("last_error", "My last reply didn't finish."))
    if st.button("Retry"):
        st.session_state.pop("last_error", None)
        # Passing None as the input means "continue the pending run from the
        # last checkpoint" rather than starting anything new.
        run_turn(graph, None, config)
        st.rerun()
