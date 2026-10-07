"""The shared state every node reads from and writes to.

Why a TypedDict and not a Pydantic model: LangGraph saves this whole dict to
Postgres after every node. Keeping it to plain JSON-friendly values (str, int,
list, dict) means a saved trip still loads after we change a Pydantic model in
`planner/models.py`. Nodes rebuild models with `Model.model_validate(state[key])`
when they need validation, and store them back with `model_dump(mode="json")`.

Why everything except `messages` is `NotRequired`: a brand-new trip starts with
only `messages`, and each phase fills in its own keys later. Readers must use
`state.get(key, default)`, never `state[key]`, for those keys.
"""

from typing import Annotated, Literal, NotRequired, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

Phase = Literal["discovery", "constraints", "selection", "planning", "done"]


class TravelState(TypedDict):
    # `add_messages` is a *reducer*: when a node returns {"messages": [msg]},
    # LangGraph appends msg to the list instead of replacing the list. Every
    # other key has no reducer, so a returned value simply overwrites it.
    messages: Annotated[list[AnyMessage], add_messages]

    # --- Phase 2: conversation control ---------------------------------------
    phase: NotRequired[Phase]          # which agent handles the next user turn
    user_turns: NotRequired[int]       # counts replies; the profiler caps discovery at 6

    # --- Filled in by later phases (see Docs/LLD.md, "State schema") ---------
    preferences: NotRequired[dict]     # Preferences
    trip: NotRequired[dict]            # TripInputs
    candidates: NotRequired[list[dict]]  # Candidate, best first
    selected: NotRequired[str]         # dest_id
    transport: NotRequired[list[dict]]   # PricedItem, written by logistics
    stays: NotRequired[list[dict]]       # PricedItem, written by logistics
    activities: NotRequired[list[dict]]  # PricedItem, written by experience
    weather: NotRequired[list[dict]]     # one row per day
    total_inr: NotRequired[int]
    budget_attempts: NotRequired[int]
    budget_target: NotRequired[Literal["logistics", "experience"]]
    budget_feedback: NotRequired[str]
    validation_status: NotRequired[Literal["ok", "best_effort"]]
    itinerary_md: NotRequired[str]
