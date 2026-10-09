"""End-to-end checks against the real services: Neon Postgres and the LLM.

Skipped by default, because they need secrets and network and spend LLM calls
(about 9 in total, which matters on a free tier of ~20 requests/day/model).
Run them before deploying:

    RUN_INTEGRATION=1 uv run pytest tests/test_integration.py -v      (bash)
    $env:RUN_INTEGRATION=1; uv run pytest tests/test_integration.py -v (PowerShell)

Each test writes a throwaway trip to the database and deletes it at the end.

A real model words things differently on every run, so these tests only check
facts any correct run must produce (saved values, the phase), never reply text.
"""

import os
import time
import uuid
from datetime import date, timedelta

import pytest
from langgraph.types import Command

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION") != "1", reason="set RUN_INTEGRATION=1 to run"
)


def test_trip_round_trip_on_neon_with_real_model():
    import planner.db
    import planner.llm
    from planner.graph.build import build_graph

    checkpointer = planner.db.get_checkpointer()  # also creates LangGraph's tables
    thread_id = f"integration-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}
    try:
        graph = build_graph(planner.llm.get_llm(), checkpointer)
        graph.invoke({"messages": []}, config)
        graph.invoke(Command(resume="I want somewhere quiet near the sea."), config)

        # A second graph instance stands in for a restarted app.
        fresh = build_graph(planner.llm.get_llm(), checkpointer)
        snap = fresh.get_state(config)
        messages = snap.values["messages"]
        assert len(messages) == 3
        assert messages[-1].content.strip()  # the model actually replied
        assert snap.interrupts  # paused, waiting for the next turn
    finally:
        checkpointer.delete_thread(thread_id)

    assert not checkpointer.get_tuple(config)  # cleanup worked


# Free tiers also limit requests per minute; each turn below makes 2 LLM calls.
PAUSE_SECONDS = float(os.environ.get("INTEGRATION_PAUSE", "6"))


def test_phase3_conversation_reaches_selection_and_can_change_details():
    """Greeting -> discovery -> constraints -> selection -> change details -> selection."""
    import planner.db
    import planner.llm
    from planner.graph.build import build_graph
    from planner.graph.nodes.chat import CHANGE_DETAILS

    # A date well in the future, written with its year, so the test never
    # depends on what "today" is or on how the model resolves a bare date.
    leave = date.today() + timedelta(days=45)
    checkpointer = planner.db.get_checkpointer()
    thread_id = f"integration-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    def say(answer):
        time.sleep(PAUSE_SECONDS)
        graph.invoke(Command(resume=answer), config)
        return graph.get_state(config).values

    try:
        graph = build_graph(planner.llm.get_llm(), checkpointer)
        graph.invoke({"messages": []}, config)

        # Everything the profiler needs in one message.
        values = say("I'd love misty hills, a calm and slow trip, and lots of great local food.")
        prefs = values["preferences"]
        assert "hills" in prefs["settings"] and "calm" in prefs["moods"]
        assert "food" in prefs["interests"] and prefs["pace"] == "slow"
        assert values["phase"] == "constraints"

        # Everything the constraints node needs in one message.
        values = say(f"Two adults from Pune, leaving on {leave:%d %B %Y} for 4 nights, "
                     "total budget 60000 rupees, train only.")
        trip = values["trip"]
        assert trip["origin_city"].lower() == "pune"
        assert trip["start_date"] == leave.isoformat()
        assert (trip["nights"], trip["adults"], trip["budget_inr"]) == (4, 2, 60000)
        assert trip["modes"] == ["train"]
        assert values["phase"] == "selection" and values["trip_problems"] == []

        # The "Change trip details" button, then the change itself.
        values = say(CHANGE_DETAILS)
        assert values["phase"] == "constraints"  # waits for the user's answer
        values = say("Make it 6 nights please.")
        assert values["phase"] == "selection"
        assert values["trip"]["nights"] == 6
        assert values["trip"]["budget_inr"] == 60000  # the rest is kept

        # Every user turn got a non-empty reply from the chat node.
        replies = [m for m in values["messages"] if m.type == "ai"]
        assert len(replies) == 5 and all(m.content.strip() for m in replies)
    finally:
        checkpointer.delete_thread(thread_id)

    assert not checkpointer.get_tuple(config)
