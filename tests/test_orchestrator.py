"""Routing functions are pure, so each case is one line and needs no fixtures."""

import pytest

from planner.graph.nodes.orchestrator import route


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
