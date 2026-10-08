"""Tests for the chat node's phase-aware prompt. build_prompt is plain Python,
so these check the exact instructions the model gets, with no model at all."""

from datetime import date

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from planner.graph.nodes.chat import PREFERENCE_TOPICS, TRIP_TOPICS, build_prompt, make_chat
from tests.fakes import RecordingModel

TODAY = date(2026, 10, 8)
PREFS = {"settings": ["hills"], "moods": ["calm"], "interests": ["food"], "pace": "slow"}
TRIP = {"origin_city": "Pune", "start_date": "2026-11-20", "nights": 4,
        "adults": 2, "budget_inr": 60000, "modes": ["train"]}


def prompt(**state):
    state.setdefault("messages", [])
    return build_prompt(state, TODAY)


# --- every phase ---------------------------------------------------------------

def test_prompt_has_todays_date_and_the_no_invention_rule():
    text = prompt()
    assert "Thursday 08 October 2026" in text
    assert "Never suggest destinations" in text


# --- discovery -----------------------------------------------------------------

def test_new_trip_asks_about_setting_first():
    text = prompt()  # no phase yet counts as discovery
    assert PREFERENCE_TOPICS["settings"] in text


def test_discovery_asks_about_the_next_missing_preference():
    text = prompt(phase="discovery", preferences={"settings": ["hills"], "moods": ["calm"]})
    assert PREFERENCE_TOPICS["interests"] in text
    assert PREFERENCE_TOPICS["settings"] not in text  # already known
    assert '"hills"' in text  # what's known is shown


def test_discovery_with_everything_known_still_has_a_question():
    # Only happens if the profiler hasn't moved on yet; chat must not break.
    text = prompt(phase="discovery", preferences=PREFS)
    assert "anything else" in text


# --- constraints ---------------------------------------------------------------

def test_first_constraints_turn_reflects_preferences_then_asks_origin():
    text = prompt(phase="constraints", preferences=PREFS)
    assert "Reflect their preferences back" in text
    assert TRIP_TOPICS["origin_city"] in text


def test_constraints_asks_about_the_next_missing_trip_field():
    text = prompt(phase="constraints", preferences=PREFS,
                  trip={"origin_city": "Pune", "start_date": "2026-11-20"})
    assert TRIP_TOPICS["nights"] in text
    assert "Reflect their preferences back" not in text  # only on the first turn
    assert '"Pune"' in text


def test_rejected_value_is_explained_before_anything_else():
    problem = "The start date 01 October 2026 has already passed (today is 08 October 2026)."
    text = prompt(phase="constraints", preferences=PREFS, trip=TRIP, trip_problems=[problem])
    assert problem in text
    assert "Explain this kindly" in text
    assert "Ask about" not in text  # one thing at a time: fix the problem first


def test_rejected_value_on_first_constraints_turn_skips_the_recap():
    problem = "The start date 01 October 2026 has already passed (today is 08 October 2026)."
    text = prompt(phase="constraints", preferences=PREFS, trip_problems=[problem])
    assert "Reflect their preferences back" not in text
    assert problem in text


# --- selection and later ----------------------------------------------------------

def test_selection_summarises_and_names_no_destinations():
    text = prompt(phase="selection", preferences=PREFS, trip=TRIP)
    assert "All the details are collected" in text
    assert '"Pune"' in text and '"hills"' in text
    assert "Don't name any destinations" in text


# --- the node ------------------------------------------------------------------

def test_chat_node_sends_the_built_prompt_and_returns_the_reply():
    model = RecordingModel(responses=["Where are you starting from?"], calls=[])
    state = {"phase": "constraints", "preferences": PREFS,
             "messages": [AIMessage("Hi"), HumanMessage("calm hills")]}

    update = make_chat(model, today=lambda: TODAY)(state)

    system = model.calls[-1][0]
    assert isinstance(system, SystemMessage)
    assert system.content == build_prompt(state, TODAY)
    assert update["messages"][0].content == "Where are you starting from?"


# --- "Change trip details" ------------------------------------------------------

def test_edit_turn_lists_details_and_asks_what_to_change():
    text = prompt(phase="constraints", preferences=PREFS, trip=TRIP,
                  user_turns=5, trip_edit_turn=5)
    assert "They want to change their trip details" in text
    assert "Reflect their preferences back" not in text
    assert "Ask about" not in text


def test_turn_after_edit_is_a_normal_constraints_turn():
    text = prompt(phase="constraints", preferences=PREFS, trip=TRIP,
                  user_turns=6, trip_edit_turn=5)
    assert "They want to change their trip details" not in text


def test_wait_for_user_turns_the_button_into_an_edit_request(monkeypatch):
    import planner.graph.nodes.chat as chat

    monkeypatch.setattr(chat, "interrupt", lambda value: chat.CHANGE_DETAILS)
    update = chat.wait_for_user({"phase": "selection", "user_turns": 4})

    assert update["phase"] == "constraints"
    assert update["user_turns"] == 5 and update["trip_edit_turn"] == 5
    assert update["messages"][0].content == chat.CHANGE_DETAILS_TEXT


def test_wait_for_user_rejects_unknown_actions(monkeypatch):
    import pytest

    import planner.graph.nodes.chat as chat

    monkeypatch.setattr(chat, "interrupt", lambda value: {"action": "delete_everything"})
    with pytest.raises(ValueError):
        chat.wait_for_user({"user_turns": 1})
