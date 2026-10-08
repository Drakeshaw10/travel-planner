"""The conversation nodes: greet, wait_for_user and chat.

A LangGraph node is a function `state -> dict`. The dict holds only the keys the
node changes; LangGraph merges it into the state and saves a checkpoint.
"""

import json
from collections.abc import Callable
from datetime import date

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import interrupt

from planner.llm import MAX_HISTORY
from planner.models import Preferences, TripInputs

GREETING = (
    "Hi! Let's find you a trip without you having to pick a place first. "
    "To start: right now, would you rather hear waves or birdsong?"
)

PERSONA = """You are a warm, curious travel companion for people in India who don't know
where they want to go yet. Keep replies short: one or two sentences, then ONE
question. Never suggest destinations, hotels or prices yourself: those come
from the planner's own data later, and anything you invent would be wrong.
Today is {today}."""

# What to ask about for each missing preference, in asking order. The examples
# steer answers towards the tags the profiler can store (planner/models.py).
PREFERENCE_TOPICS = {
    "settings": "what kind of place appeals (beach, hills, forest, desert, backwaters, heritage towns, a city)",
    "moods": "the mood they want (calm, adventurous, romantic, social, spiritual)",
    "interests": "what they enjoy doing (food, trekking, wildlife, temples, history, nightlife, water sports, photography, wellness)",
    "pace": "how full the days should be (slow, balanced or packed)",
}

# What to ask for each missing trip field, keyed by TripInputs.missing() names.
TRIP_TOPICS = {
    "origin_city": "which city they will travel from",
    "start_date": "the date they want to leave",
    "nights": "how many nights they will be away",
    "adults": "how many people are travelling (adults, plus any children under 12)",
    "budget_inr": "their total budget for the whole group, in rupees",
    "modes": "how they are happy to travel: flight, train and/or bus",
}


def _known(model) -> str:
    """The non-empty fields of a model as compact JSON, for the prompt."""
    return json.dumps(model.model_dump(mode="json", exclude_none=True, exclude_defaults=True))


def build_prompt(state, today: date) -> str:
    """Write the chat node's instructions for this turn from the state.

    Why build it from state instead of one fixed prompt: the right next question
    depends on where the conversation is. The extracting nodes (profiler,
    constraints) have just updated `preferences`, `trip` and `trip_problems`,
    and this function turns that into "ask about X next". It is plain Python
    with no LLM call, so every case is unit-tested exactly.
    """
    phase = state.get("phase", "discovery")
    prefs = Preferences.model_validate(state.get("preferences", {}))
    trip = TripInputs.model_validate(state.get("trip", {}))
    parts = [PERSONA.format(today=f"{today:%A %d %B %Y}")]

    if phase == "discovery":
        missing = [f for f in PREFERENCE_TOPICS if not getattr(prefs, f)]
        topic = PREFERENCE_TOPICS[missing[0]] if missing else "anything else that would make the trip special"
        parts.append(
            "You are getting to know what kind of trip they want.\n"
            f"Known so far: {_known(prefs)}\n"
            f"Ask, in a friendly and natural way, about {topic}."
        )

    elif phase == "constraints":
        problems = state.get("trip_problems", [])
        missing = trip.missing()
        lines = [f"Their trip preferences are settled: {_known(prefs)}",
                 f"Trip details known so far: {_known(trip)}"]
        if not any(getattr(trip, f) for f in TRIP_TOPICS) and not problems and not is_edit_turn(state):
            # First turn of this phase: the profiler has just finished.
            lines.append("Reflect their preferences back in one short sentence so they "
                         "feel heard, then move on to the practical details.")
        if is_edit_turn(state):
            # The user clicked "Change trip details": show what is saved so
            # they can see what to change, and let them answer in their own words.
            lines.append("They want to change their trip details. List the current details "
                         "briefly (one short line each, in plain words, not JSON) and ask "
                         "what they would like to change. Say that if everything is fine "
                         "they can just say so.")
        elif problems:
            # A value the user gave was rejected (constraints node). Say so
            # plainly first, or their request just looks ignored.
            lines.append("Something they said could not be used: " + " ".join(problems)
                         + " Explain this kindly and ask them to correct it.")
        elif missing:
            lines.append(f"Ask about {TRIP_TOPICS[missing[0]]}.")
        parts.append("\n".join(lines))

    else:  # "selection", "planning", "done": everything needed has been collected
        parts.append(
            "All the details are collected.\n"
            f"Preferences: {_known(prefs)}\nTrip: {_known(trip)}\n"
            "If you haven't already, summarise the trip in one or two lines and say "
            "that matching destinations is the next step. Otherwise answer their "
            "question briefly. Don't name any destinations."
        )

    return "\n\n".join(parts)


# The resume value app.py sends when "Change trip details" is clicked.
CHANGE_DETAILS = {"action": "change_details"}
CHANGE_DETAILS_TEXT = "I'd like to change my trip details."


def greet(state) -> dict:
    """First node of every trip. A fixed message, so opening a trip costs no LLM call."""
    return {"messages": [AIMessage(GREETING)], "phase": "discovery"}


def wait_for_user(state) -> dict:
    """Pause the graph until the user replies, then add their reply to the history.

    How `interrupt()` works, because it is the core of human-in-the-loop:
    1. The first time this node runs, `interrupt()` raises a special signal.
       LangGraph stops the run and saves a checkpoint that says "paused here".
       The Streamlit script finishes; nothing is kept in memory.
    2. When the user types, app.py calls the graph with `Command(resume=text)`.
       LangGraph loads the checkpoint and runs this node again *from its first
       line*. This time `interrupt()` returns `text` instead of pausing.

    Because the node re-runs from the top, nothing before `interrupt()` may have
    side effects (no API calls, no database writes): they would happen twice.
    """
    answer = interrupt("waiting_for_user")
    turn = state.get("user_turns", 0) + 1

    # A button click arrives as a small dict instead of text. Only actions on
    # this allowlist are accepted: resume values come from outside the graph.
    if answer == CHANGE_DETAILS:
        return {
            # Shown in the chat like a typed message, so the history explains
            # why the conversation went back to trip details.
            "messages": [HumanMessage(CHANGE_DETAILS_TEXT)],
            "user_turns": turn,
            "phase": "constraints",
            "trip_edit_turn": turn,
        }

    if not isinstance(answer, str) or not answer.strip():
        # Resume values come from outside the graph, so check them like any
        # user input instead of trusting them.
        raise ValueError("wait_for_user must be resumed with non-empty text or a known action")
    return {
        "messages": [HumanMessage(answer.strip())],
        "user_turns": turn,
    }


def is_edit_turn(state) -> bool:
    """True on the turn the user clicked "Change trip details"."""
    return state.get("trip_edit_turn") is not None and state.get("trip_edit_turn") == state.get("user_turns")


def make_chat(llm: BaseChatModel, today: Callable[[], date] = date.today):
    """Build the `chat` node around a given model and clock.

    Why a factory instead of calling `get_llm()` inside the node: the node gets
    its model passed in (dependency injection). Production passes the real
    model; tests pass a fake one. The node never knows the difference, and the
    graph package never touches secrets. `today` is injected for the same
    reason as in the constraints node.
    """

    def chat(state) -> dict:
        # The instructions change every turn (see build_prompt); the history is
        # capped to the most recent messages to bound cost and latency.
        history = [SystemMessage(build_prompt(state, today())), *state["messages"][-MAX_HISTORY:]]
        # `invoke`, not `stream`: when app.py runs the graph with
        # stream_mode="messages", LangGraph hooks into this call and forwards
        # each token to the UI as it arrives. The node itself still gets back
        # one complete AIMessage to store in state.
        reply = llm.invoke(history)
        return {"messages": [reply]}

    return chat
