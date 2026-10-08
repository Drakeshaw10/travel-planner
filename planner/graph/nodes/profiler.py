"""The profiler node: turns discovery chat into structured `Preferences`.

It runs after every user message while `phase == "discovery"`. It doesn't talk
to the user: it reads the conversation, updates `state["preferences"]`, and
decides whether discovery is finished. The `chat` node runs next and asks the
follow-up question.
"""

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from planner.graph.nodes.extraction import extract
from planner.models import AVOIDS, INTERESTS, MOODS, SETTINGS, Preferences

# How many recent messages the extractor reads (LLD.md: "last 10 messages").
# Older answers are already captured in `preferences`, which goes in the prompt.
RECENT_MESSAGES = 10

# Stop asking after this many user turns even if preferences are incomplete,
# so a vague user isn't stuck in discovery forever (LLD.md "Limits").
MAX_DISCOVERY_TURNS = 6

SYSTEM_PROMPT = """\
You extract travel preferences from a conversation with someone in India who
doesn't yet know where they want to go.

Use ONLY these tags. Never invent a tag; pick the closest one or leave it out.
- settings: {settings}
- moods: {moods}
- interests: {interests}
- avoid: {avoid}
- pace: slow, balanced or packed

Preferences already known:
{current}

Return the full, updated preferences:
- Keep the known tags unless the user has changed their mind; then remove them.
- Add tags for anything new the user said, even indirectly
  ("I love the sound of waves" means settings: beach).
- Leave a field empty or null if the user hasn't said anything about it.
"""


def build_prompt(current: Preferences) -> str:
    """Fill the prompt with the vocabulary and the current preferences.

    Why the current preferences go in: merged() *replaces* lists, so the model
    must return the full list, old tags included. It can only do that if it
    sees them, and seeing them is also what lets it remove one when the user
    changes their mind.
    """
    return SYSTEM_PROMPT.format(
        settings=", ".join(SETTINGS),
        moods=", ".join(MOODS),
        interests=", ".join(INTERESTS),
        avoid=", ".join(AVOIDS),
        current=json.dumps(current.model_dump(mode="json"), indent=2),
    )


def make_profiler(llm: BaseChatModel):
    """Build the profiler node around a given model (see make_chat for why a factory)."""
    # json_schema: chosen by the Step 2 spike (scripts/spike_structured_output.py).
    # include_raw=True: return parse errors instead of raising, so extract() can retry
    # (see planner/graph/nodes/extraction.py).
    extractor = llm.with_structured_output(Preferences, method="json_schema", include_raw=True)

    def profiler(state) -> dict:
        current = Preferences.model_validate(state.get("preferences", {}))
        messages = [SystemMessage(build_prompt(current)), *state["messages"][-RECENT_MESSAGES:]]

        found = extract(extractor, messages, "profiler")
        updated = current.merged(found) if found else current

        update = {"preferences": updated.model_dump(mode="json")}
        if updated.is_complete() or state.get("user_turns", 0) >= MAX_DISCOVERY_TURNS:
            update["phase"] = "constraints"
        return update

    return profiler
