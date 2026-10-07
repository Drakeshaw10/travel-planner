"""End-to-end check against the real services: Neon Postgres and the HF model.

Skipped by default, because it needs secrets and network and spends a few LLM
tokens. Run it before deploying:

    RUN_INTEGRATION=1 uv run pytest tests/test_integration.py -v      (bash)
    $env:RUN_INTEGRATION=1; uv run pytest tests/test_integration.py -v (PowerShell)

It writes one throwaway trip to the database and deletes it at the end.
"""

import os
import uuid

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
