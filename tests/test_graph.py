"""Run the real graph with a fake model and an in-memory checkpointer.

InMemorySaver behaves like PostgresSaver but keeps checkpoints in a dict, so
these tests check pause/resume/retry logic without a database.
"""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from planner.graph.build import ROUTE_MAP, build_graph
from planner.graph.nodes.chat import GREETING
from planner.llm import MAX_HISTORY
from tests.fakes import FlakyModel, RecordingModel


def config(thread_id="trip-1"):
    return {"configurable": {"thread_id": thread_id}}


def start(graph, thread_id="trip-1"):
    graph.invoke({"messages": []}, config(thread_id))


def test_new_trip_greets_and_waits():
    graph = build_graph(FakeListChatModel(responses=["unused"]), InMemorySaver())
    start(graph)

    snap = graph.get_state(config())
    assert [m.content for m in snap.values["messages"]] == [GREETING]
    assert snap.values["phase"] == "discovery"
    assert snap.next == ("wait_for_user",)
    assert snap.interrupts and snap.interrupts[0].value == "waiting_for_user"


def test_resume_adds_user_message_and_reply():
    graph = build_graph(FakeListChatModel(responses=["Waves it is!"]), InMemorySaver())
    start(graph)

    graph.invoke(Command(resume="  Waves, definitely  "), config())

    snap = graph.get_state(config())
    msgs = snap.values["messages"]
    assert [type(m) for m in msgs] == [AIMessage, HumanMessage, AIMessage]
    assert msgs[1].content == "Waves, definitely"  # whitespace trimmed
    assert msgs[2].content == "Waves it is!"
    assert snap.values["user_turns"] == 1
    assert snap.interrupts  # paused again, waiting for the next message


def test_empty_resume_is_rejected():
    graph = build_graph(FakeListChatModel(responses=["unused"]), InMemorySaver())
    start(graph)
    with pytest.raises(ValueError):
        graph.invoke(Command(resume="   "), config())


def test_stream_messages_only_from_chat_node():
    graph = build_graph(FakeListChatModel(responses=["Hello"]), InMemorySaver())
    start(graph)

    nodes, text = set(), ""
    for chunk, meta in graph.stream(Command(resume="hi"), config(), stream_mode="messages"):
        nodes.add(meta["langgraph_node"])
        if meta["langgraph_node"] == "chat":
            text += chunk.content
    assert text == "Hello"
    # The user's message from wait_for_user may also appear in the stream;
    # app.py filters it out by node name.
    assert nodes <= {"chat", "wait_for_user"}


def test_failed_node_can_be_retried_from_checkpoint():
    graph = build_graph(FlakyModel(responses=["Recovered"], fail_times=1), InMemorySaver())
    start(graph)

    with pytest.raises(TimeoutError):
        graph.invoke(Command(resume="hills"), config())

    snap = graph.get_state(config())
    assert snap.next == ("chat",)  # stopped before chat finished
    assert not snap.interrupts  # so there is nothing for user text to resume
    assert snap.values["messages"][-1].content == "hills"  # user message kept

    graph.invoke(None, config())  # Retry: continue from the last checkpoint
    snap = graph.get_state(config())
    assert snap.values["messages"][-1].content == "Recovered"
    assert snap.interrupts


def test_state_survives_a_new_graph_instance():
    """Simulates an app restart: a fresh graph on the same saver sees the trip."""
    saver = InMemorySaver()
    first = build_graph(FakeListChatModel(responses=["One"]), saver)
    start(first)
    first.invoke(Command(resume="hello"), config())

    second = build_graph(FakeListChatModel(responses=["Two"]), saver)
    second.invoke(Command(resume="again"), config())

    contents = [m.content for m in second.get_state(config()).values["messages"]]
    assert contents == [GREETING, "hello", "One", "again", "Two"]


def test_trips_are_isolated_by_thread_id():
    graph = build_graph(FakeListChatModel(responses=["A", "B"]), InMemorySaver())
    start(graph, "trip-a")
    start(graph, "trip-b")
    graph.invoke(Command(resume="only in a"), config("trip-a"))

    assert len(graph.get_state(config("trip-a")).values["messages"]) == 3
    assert len(graph.get_state(config("trip-b")).values["messages"]) == 1


def test_chat_sends_only_recent_history():
    model = RecordingModel(responses=["ok"], calls=[])
    graph = build_graph(model, InMemorySaver())
    start(graph)
    for i in range(12):  # greeting + 12 turns x 2 messages, then the last reply
        graph.invoke(Command(resume=f"answer {i}"), config())

    sent = model.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert len(sent) == 1 + MAX_HISTORY
    assert sent[-1].content == "answer 11"


def test_route_map_only_points_at_existing_nodes():
    graph = build_graph(FakeListChatModel(responses=["x"]), InMemorySaver())
    assert set(ROUTE_MAP.values()) <= set(graph.nodes)
