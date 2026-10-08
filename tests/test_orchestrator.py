"""Routing functions are pure, so each case is one line and needs no fixtures."""

import pytest

from planner.graph.nodes.orchestrator import after_constraints, route


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        (None, "profiler"),  # a trip with no phase yet starts in discovery
        ("discovery", "profiler"),
        ("constraints", "constraints"),
        ("selection", "chat"),
        ("planning", "chat"),
        ("done", "chat"),
    ],
)
def test_route(phase, expected):
    state = {} if phase is None else {"phase": phase}
    assert route(state) == expected


@pytest.mark.parametrize(
    ("phase", "expected"),
    [
        ("selection", "scorer"),  # trip fully described: go and score destinations
        ("constraints", "chat"),  # something missing or rejected: ask about it
        (None, "chat"),
    ],
)
def test_after_constraints(phase, expected):
    state = {} if phase is None else {"phase": phase}
    assert after_constraints(state) == expected
