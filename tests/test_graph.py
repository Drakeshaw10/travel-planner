"""Run the real graph with a fake model and an in-memory checkpointer.

InMemorySaver behaves like PostgresSaver but keeps checkpoints in a dict, so
these tests check pause/resume/retry logic without a database.
"""

from datetime import date

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from planner.graph.build import AFTER_CONSTRAINTS_MAP, ROUTE_MAP, build_graph
from planner.graph.nodes.chat import CHANGE_DETAILS, CHANGE_DETAILS_TEXT, GREETING
from planner.graph.nodes.profiler import MAX_DISCOVERY_TURNS
from planner.llm import MAX_HISTORY
from planner.models import Preferences, TripInputs
from tests.fakes import FakeChat, FlakyModel, RecordingModel


def config(thread_id="trip-1"):
    return {"configurable": {"thread_id": thread_id}}


def start(graph, thread_id="trip-1"):
    graph.invoke({"messages": []}, config(thread_id))


def test_new_trip_greets_and_waits():
    graph = build_graph(FakeChat(responses=["unused"]), InMemorySaver())
    start(graph)

    snap = graph.get_state(config())
    assert [m.content for m in snap.values["messages"]] == [GREETING]
    assert snap.values["phase"] == "discovery"
    assert snap.next == ("wait_for_user",)
    assert snap.interrupts and snap.interrupts[0].value == "waiting_for_user"


def test_resume_adds_user_message_and_reply():
    graph = build_graph(FakeChat(responses=["Waves it is!"]), InMemorySaver())
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
    graph = build_graph(FakeChat(responses=["unused"]), InMemorySaver())
    start(graph)
    with pytest.raises(ValueError):
        graph.invoke(Command(resume="   "), config())


def test_stream_messages_only_from_chat_node():
    graph = build_graph(FakeChat(responses=["Hello"]), InMemorySaver())
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
    first = build_graph(FakeChat(responses=["One"]), saver)
    start(first)
    first.invoke(Command(resume="hello"), config())

    second = build_graph(FakeChat(responses=["Two"]), saver)
    second.invoke(Command(resume="again"), config())

    contents = [m.content for m in second.get_state(config()).values["messages"]]
    assert contents == [GREETING, "hello", "One", "again", "Two"]


def test_trips_are_isolated_by_thread_id():
    graph = build_graph(FakeChat(responses=["A", "B"]), InMemorySaver())
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


def test_route_maps_only_point_at_existing_nodes():
    graph = build_graph(FakeChat(responses=["x"]), InMemorySaver())
    assert set(ROUTE_MAP.values()) <= set(graph.nodes)
    assert set(AFTER_CONSTRAINTS_MAP.values()) <= set(graph.nodes)


# --- Phase 3: profiler and constraints wired in ------------------------------

PREFS = Preferences(settings=["hills"], moods=["calm"], interests=["food"], pace="slow")
TRIP = TripInputs(origin_city="Pune", start_date=date(2026, 11, 20), nights=4,
                  adults=2, budget_inr=60000, modes=["train"])


def phase3_graph(extractions, replies=None):
    """A graph whose fake model answers chat with "ok" and extractions in order."""
    model = FakeChat(responses=replies or ["ok"], extractions=list(extractions))
    return build_graph(model, InMemorySaver(), today=lambda: date(2026, 10, 8))


def nodes_run(graph, text, thread="trip-1"):
    """Send one user message and return the names of the nodes that ran, in order."""
    updates = graph.stream(Command(resume=text), config(thread), stream_mode="updates")
    return [name for update in updates for name in update if name != "__interrupt__"]


def test_discovery_turn_runs_profiler_then_chat():
    graph = phase3_graph([Preferences(settings=["hills"])])
    start(graph)

    assert nodes_run(graph, "misty hills please") == ["wait_for_user", "profiler", "chat"]
    snap = graph.get_state(config())
    assert snap.values["preferences"]["settings"] == ["hills"]
    assert snap.values["phase"] == "discovery"


def test_complete_preferences_hand_over_to_constraints_next_turn():
    graph = phase3_graph([PREFS, TripInputs(origin_city="Pune")])
    start(graph)

    nodes_run(graph, "calm hills, food, slow")  # profiler completes preferences
    assert graph.get_state(config()).values["phase"] == "constraints"

    assert nodes_run(graph, "from Pune") == ["wait_for_user", "constraints", "chat"]
    assert graph.get_state(config()).values["trip"]["origin_city"] == "Pune"


def test_complete_trip_moves_to_selection():
    graph = phase3_graph([PREFS, TRIP])
    start(graph)
    nodes_run(graph, "calm hills, food, slow")
    nodes_run(graph, "everything at once")

    values = graph.get_state(config()).values
    assert values["phase"] == "selection"
    assert values["trip_problems"] == []
    # No scorer yet: AFTER_CONSTRAINTS_MAP sends "scorer" to chat, and the
    # graph pauses for the user as usual.
    assert graph.get_state(config()).interrupts


def test_rejected_value_keeps_the_trip_in_constraints():
    past = TRIP.model_copy(update={"start_date": date(2026, 10, 1)})
    graph = phase3_graph([PREFS, past])
    start(graph)
    nodes_run(graph, "calm hills, food, slow")
    nodes_run(graph, "start 1st October")

    values = graph.get_state(config()).values
    assert values["phase"] == "constraints"
    assert values["trip"]["start_date"] is None
    assert "already passed" in values["trip_problems"][0]


def test_discovery_turn_cap_moves_on_with_incomplete_preferences():
    graph = phase3_graph([])  # the profiler never learns anything
    start(graph)
    for i in range(MAX_DISCOVERY_TURNS):
        nodes_run(graph, f"not sure {i}")

    assert graph.get_state(config()).values["phase"] == "constraints"


def test_selection_phase_messages_go_to_chat():
    graph = phase3_graph([PREFS, TRIP])
    start(graph)
    nodes_run(graph, "calm hills, food, slow")
    nodes_run(graph, "everything at once")

    assert nodes_run(graph, "so where should we go?") == ["wait_for_user", "chat"]


def test_change_details_goes_back_to_constraints_then_returns():
    graph = phase3_graph([PREFS, TRIP, TripInputs(), TripInputs(nights=6)])
    start(graph)
    nodes_run(graph, "calm hills, food, slow")
    nodes_run(graph, "everything at once")
    assert graph.get_state(config()).values["phase"] == "selection"

    # The button: resume with the action instead of text.
    ran = [n for u in graph.stream(Command(resume=CHANGE_DETAILS), config(), stream_mode="updates")
           for n in u if n != "__interrupt__"]
    values = graph.get_state(config()).values
    assert ran == ["wait_for_user", "constraints", "chat"]
    assert values["phase"] == "constraints"  # stays while the user decides
    assert values["messages"][-2].content == CHANGE_DETAILS_TEXT

    nodes_run(graph, "make it 6 nights")
    values = graph.get_state(config()).values
    assert values["phase"] == "selection"
    assert values["trip"]["nights"] == 6
    assert values["trip"]["origin_city"] == "Pune"  # everything else kept
