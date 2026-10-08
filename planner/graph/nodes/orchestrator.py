"""Routing functions for every conditional edge in the graph.

Why they live together and stay this small: a routing function only *reads*
state and returns the name of the next node. It never calls the LLM, an API or
the database. That makes each one a pure function you can unit-test in one line,
and keeps "who runs next" in a single file you can read top to bottom.
"""

from typing import Literal


def route(state) -> Literal["profiler", "constraints", "chat"]:
    """After `wait_for_user`: pick the agent for this user turn from `phase`."""
    match state.get("phase", "discovery"):
        case "discovery":
            return "profiler"
        case "constraints":
            return "constraints"
        case _:
            # "selection", "planning" and "done": the user is chatting about
            # the shortlist or the finished plan.
            return "chat"


def after_constraints(state) -> Literal["scorer", "chat"]:
    """After `constraints`: score destinations once the trip is fully described.

    The constraints node sets phase="selection" only when nothing is missing and
    nothing the user said was rejected. Until then `chat` asks the next question.
    """
    return "scorer" if state.get("phase") == "selection" else "chat"
