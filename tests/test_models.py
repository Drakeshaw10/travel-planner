"""Tests for planner/models.py: plain Python, no LLM or network."""

from datetime import date

import pytest
from pydantic import ValidationError

from planner.models import SETTINGS, Preferences, TripInputs


# --- Preferences -------------------------------------------------------------

def test_empty_preferences_are_incomplete():
    assert not Preferences().is_complete()


def test_preferences_complete_without_avoid():
    prefs = Preferences(settings=["beach"], moods=["calm"], interests=["food"], pace="slow")
    assert prefs.is_complete()


def test_unknown_tags_are_dropped_not_rejected():
    prefs = Preferences(settings=["beach", "moon", "seaside"])
    assert prefs.settings == ["beach"]


def test_tags_are_normalised_and_deduplicated():
    prefs = Preferences(settings=["  Beach", "beach", "HILLS"])
    assert prefs.settings == ["beach", "hills"]


def test_single_tag_string_becomes_a_list():
    assert Preferences(moods="calm").moods == ["calm"]


def test_null_tag_list_becomes_empty():
    assert Preferences(interests=None).interests == []


def test_bad_pace_is_rejected():
    # pace is one value, not a list, so there is nothing to keep: it fails.
    with pytest.raises(ValidationError):
        Preferences(pace="lazy")


def test_vocabulary_tuple_matches_the_type():
    assert "beach" in SETTINGS and "moon" not in SETTINGS


# --- TripInputs --------------------------------------------------------------

def test_new_trip_is_missing_everything_in_order():
    assert TripInputs().missing() == [
        "origin_city", "start_date", "nights", "adults", "budget_inr", "modes",
    ]


def test_complete_trip_is_missing_nothing():
    trip = TripInputs(origin_city="Pune", start_date=date(2026, 11, 20), nights=3,
                      adults=2, budget_inr=40000, modes=["train"])
    assert trip.missing() == []


@pytest.mark.parametrize(
    "bad",
    [{"nights": 0}, {"nights": 15}, {"adults": 0}, {"adults": 7},
     {"children": -1}, {"children": 5}, {"budget_inr": 0}],
)
def test_limits_are_enforced(bad):
    with pytest.raises(ValidationError):
        TripInputs(**bad)


def test_unknown_mode_is_dropped():
    assert TripInputs(modes=["Train", "rocket"]).modes == ["train"]


def test_travellers_counts_unknown_children_as_zero():
    assert TripInputs(adults=2).travellers == 2
    assert TripInputs(adults=2, children=1).travellers == 3


def test_json_round_trip_keeps_date_type():
    # Graph state stores models as JSON, so this round trip happens on every turn.
    trip = TripInputs(start_date=date(2026, 11, 20), nights=3)
    stored = trip.model_dump(mode="json")
    assert stored["start_date"] == "2026-11-20"  # a plain string in state
    restored = TripInputs.model_validate(stored)
    assert restored.start_date == date(2026, 11, 20)  # a real date again
    assert restored == trip


# --- merged() ----------------------------------------------------------------

def test_merge_keeps_old_values_when_new_says_nothing():
    old = TripInputs(origin_city="Pune", nights=3)
    new = TripInputs(budget_inr=40000)
    result = old.merged(new)
    assert (result.origin_city, result.nights, result.budget_inr) == ("Pune", 3, 40000)


def test_merge_replaces_values_the_new_answer_gives():
    old = TripInputs(origin_city="Pune", nights=3)
    assert old.merged(TripInputs(nights=5)).nights == 5


def test_merge_replaces_lists_so_users_can_take_things_back():
    old = Preferences(settings=["beach", "hills"])
    assert old.merged(Preferences(settings=["hills"])).settings == ["hills"]


def test_merge_ignores_empty_lists():
    old = Preferences(settings=["beach"])
    assert old.merged(Preferences(settings=[])).settings == ["beach"]


def test_merge_keeps_an_explicit_zero():
    # Why children defaults to None: 0 is a real answer and must be stored.
    old = TripInputs(children=2)
    assert old.merged(TripInputs(children=0)).children == 0


def test_merge_does_not_change_the_original():
    old = Preferences(pace="slow")
    old.merged(Preferences(pace="packed"))
    assert old.pace == "slow"
