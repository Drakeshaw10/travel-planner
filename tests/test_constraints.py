"""Tests for the constraints node, using StructuredFake and a fixed "today"."""

from datetime import date

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from planner.graph.nodes.constraints import RECENT_MESSAGES, drop_past_date, make_constraints
from planner.models import TripInputs
from tests.fakes import StructuredFake

TODAY = date(2026, 10, 8)  # a Thursday


def fixed_today():
    return TODAY


COMPLETE = TripInputs(origin_city="Pune", start_date=date(2026, 11, 20), nights=4,
                      adults=2, budget_inr=60000, modes=["train"])


def state(*, trip=None, messages=None):
    return {
        "messages": messages or [AIMessage("Where are you starting from?"), HumanMessage("Pune")],
        "trip": trip or {},
        "phase": "constraints",
    }


def node(results):
    fake = StructuredFake(results)
    return fake, make_constraints(fake, today=fixed_today)


def test_uses_json_schema_with_raw_output():
    fake, _ = node([])
    assert fake.options == {"schema": TripInputs, "method": "json_schema", "include_raw": True}


def test_partial_answer_is_saved_and_phase_stays():
    _, constraints = node([TripInputs(origin_city="Pune")])
    update = constraints(state())

    assert update["trip"]["origin_city"] == "Pune"
    assert "phase" not in update


def test_new_answer_is_merged_with_known_trip():
    known = TripInputs(origin_city="Pune", nights=4).model_dump(mode="json")
    _, constraints = node([TripInputs(budget_inr=60000)])

    trip = constraints(state(trip=known))["trip"]

    assert (trip["origin_city"], trip["nights"], trip["budget_inr"]) == ("Pune", 4, 60000)


def test_complete_trip_moves_to_selection():
    _, constraints = node([COMPLETE])
    update = constraints(state())

    assert update["phase"] == "selection"
    assert update["trip"]["start_date"] == "2026-11-20"  # stored as JSON text


def test_children_are_not_required():
    _, constraints = node([COMPLETE])  # COMPLETE says nothing about children
    assert constraints(state())["phase"] == "selection"


def test_past_start_date_is_dropped_and_asked_again():
    _, constraints = node([COMPLETE.model_copy(update={"start_date": date(2026, 10, 1)})])
    update = constraints(state())

    assert update["trip"]["start_date"] is None
    assert "phase" not in update  # start_date is missing again
    assert update["trip_problems"] == [
        "The start date 01 October 2026 has already passed (today is 08 October 2026)."
    ]


def test_past_date_does_not_erase_a_good_known_date_or_move_on():
    known = COMPLETE.model_dump(mode="json")
    _, constraints = node([TripInputs(start_date=date(2025, 1, 1))])

    update = constraints(state(trip=known))

    assert update["trip"]["start_date"] == "2026-11-20"
    # The trip is complete, but the user was trying to change the date: stay in
    # constraints so they can answer before anything is priced.
    assert "phase" not in update
    # The request was not silently ignored: chat can explain why.
    assert len(update["trip_problems"]) == 1 and "already passed" in update["trip_problems"][0]


def test_today_is_a_valid_start_date():
    trip, problems = drop_past_date(TripInputs(start_date=TODAY), TODAY)
    assert trip.start_date == TODAY and problems == []


def test_no_problems_when_everything_is_fine():
    _, constraints = node([COMPLETE])
    assert constraints(state())["trip_problems"] == []


def test_problems_from_an_earlier_turn_are_cleared():
    """trip_problems is rewritten every run, so a fixed problem disappears."""
    _, constraints = node([TripInputs(start_date=date(2026, 10, 1)), TripInputs(start_date=date(2026, 11, 2))])
    first = constraints(state())
    second = constraints(state(trip=first["trip"]))

    assert first["trip_problems"] and second["trip_problems"] == []
    assert second["trip"]["start_date"] == "2026-11-02"


def test_parse_error_is_retried_once():
    fake, constraints = node(["bad json", COMPLETE])
    assert constraints(state())["phase"] == "selection"
    assert len(fake.calls) == 2


def test_two_parse_errors_keep_the_known_trip():
    known = TripInputs(origin_city="Pune").model_dump(mode="json")
    _, constraints = node(["bad", "still bad"])

    update = constraints(state(trip=known))

    assert update["trip"]["origin_city"] == "Pune"
    assert "phase" not in update


def test_prompt_has_today_and_known_trip():
    known = TripInputs(origin_city="Kochi").model_dump(mode="json")
    fake, constraints = node([TripInputs()])
    constraints(state(trip=known))

    system = fake.calls[0][0]
    assert isinstance(system, SystemMessage)
    assert "2026-10-08 (Thursday)" in system.content
    assert '"Kochi"' in system.content


def test_today_is_read_on_every_run():
    """The app process can stay up past midnight, so "today" must not be cached."""
    days = iter([date(2026, 10, 8), date(2026, 10, 9)])
    fake = StructuredFake([TripInputs(), TripInputs()])
    constraints = make_constraints(fake, today=lambda: next(days))

    constraints(state())
    constraints(state())

    assert "2026-10-08" in fake.calls[0][0].content
    assert "2026-10-09" in fake.calls[1][0].content


def test_only_recent_messages_are_sent():
    history = [HumanMessage(f"msg {i}") for i in range(25)]
    fake, constraints = node([TripInputs()])
    constraints(state(messages=history))

    assert len(fake.calls[0]) == 1 + RECENT_MESSAGES
    assert fake.calls[0][-1].content == "msg 24"


def test_api_failure_propagates_for_the_retry_button():
    class Broken(StructuredFake):
        def with_structured_output(self, schema, **options):
            from langchain_core.runnables import RunnableLambda

            def fail(_):
                raise TimeoutError("provider timed out")

            return RunnableLambda(fail)

    with pytest.raises(TimeoutError):
        make_constraints(Broken([]), today=fixed_today)(state())


def test_edit_turn_does_not_move_on_even_when_complete():
    _, constraints = node([TripInputs()])  # the click message holds no new facts
    update = constraints({**state(trip=COMPLETE.model_dump(mode="json")),
                          "user_turns": 5, "trip_edit_turn": 5})
    assert "phase" not in update


def test_turn_after_edit_moves_on_with_the_change():
    _, constraints = node([TripInputs(nights=6)])
    update = constraints({**state(trip=COMPLETE.model_dump(mode="json")),
                          "user_turns": 6, "trip_edit_turn": 5})
    assert update["phase"] == "selection"
    assert update["trip"]["nights"] == 6
