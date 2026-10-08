"""Tests for the profiler node, using StructuredFake instead of a real model."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from planner.graph.nodes.profiler import MAX_DISCOVERY_TURNS, RECENT_MESSAGES, make_profiler
from planner.models import Preferences
from tests.fakes import StructuredFake

COMPLETE = Preferences(settings=["beach"], moods=["calm"], interests=["food"], pace="slow")


def state(*, preferences=None, user_turns=1, messages=None):
    return {
        "messages": messages or [AIMessage("Waves or birdsong?"), HumanMessage("Waves!")],
        "preferences": preferences or {},
        "user_turns": user_turns,
        "phase": "discovery",
    }


def test_uses_json_schema_with_raw_output():
    fake = StructuredFake([])
    make_profiler(fake)
    assert fake.options == {"schema": Preferences, "method": "json_schema", "include_raw": True}


def test_partial_answer_is_saved_and_discovery_continues():
    fake = StructuredFake([Preferences(settings=["beach"])])
    update = make_profiler(fake)(state())

    assert update["preferences"]["settings"] == ["beach"]
    assert "phase" not in update  # still in discovery


def test_new_answer_is_merged_with_known_preferences():
    known = Preferences(settings=["beach"], moods=["calm"]).model_dump(mode="json")
    fake = StructuredFake([Preferences(interests=["food"])])  # mentions only food

    update = make_profiler(fake)(state(preferences=known))

    prefs = update["preferences"]
    assert (prefs["settings"], prefs["moods"], prefs["interests"]) == (["beach"], ["calm"], ["food"])


def test_complete_preferences_move_to_constraints():
    update = make_profiler(StructuredFake([COMPLETE]))(state())
    assert update["phase"] == "constraints"


def test_turn_cap_moves_on_even_if_incomplete():
    fake = StructuredFake([Preferences(settings=["hills"])])
    update = make_profiler(fake)(state(user_turns=MAX_DISCOVERY_TURNS))
    assert update["phase"] == "constraints"


def test_parse_error_is_retried_once_with_the_error():
    fake = StructuredFake(["bad json", COMPLETE])
    update = make_profiler(fake)(state())

    assert update["phase"] == "constraints"
    assert len(fake.calls) == 2
    retry_note = fake.calls[1][-1]
    assert isinstance(retry_note, HumanMessage) and "bad json" in retry_note.content


def test_two_parse_errors_keep_old_preferences():
    known = Preferences(settings=["beach"]).model_dump(mode="json")
    fake = StructuredFake(["bad", "still bad"])

    update = make_profiler(fake)(state(preferences=known))

    assert update["preferences"]["settings"] == ["beach"]
    assert "phase" not in update
    assert len(fake.calls) == 2  # no third try


def test_prompt_shows_vocabulary_and_current_preferences():
    known = Preferences(settings=["backwaters"]).model_dump(mode="json")
    fake = StructuredFake([Preferences()])
    make_profiler(fake)(state(preferences=known))

    system = fake.calls[0][0]
    assert isinstance(system, SystemMessage)
    assert "heritage" in system.content  # vocabulary listed
    assert '"backwaters"' in system.content  # current preferences shown


def test_only_recent_messages_are_sent():
    history = [HumanMessage(f"msg {i}") for i in range(25)]
    fake = StructuredFake([Preferences()])
    make_profiler(fake)(state(messages=history))

    sent = fake.calls[0]
    assert len(sent) == 1 + RECENT_MESSAGES  # system prompt + recent messages
    assert sent[-1].content == "msg 24"


def test_api_failure_propagates_for_the_retry_button():
    class Broken(StructuredFake):
        def with_structured_output(self, schema, **options):
            from langchain_core.runnables import RunnableLambda

            def fail(_):
                raise TimeoutError("router timed out")

            return RunnableLambda(fail)

    with pytest.raises(TimeoutError):
        make_profiler(Broken([]))(state())
