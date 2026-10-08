"""Typed shapes for what the agents pull out of the conversation.

The profiler and constraints nodes ask the LLM to fill these models from chat.
LLM output is untrusted text, so every field here is checked by Pydantic before
the rest of the app uses it: wrong types, numbers out of range and unknown tags
never reach the scorer or the pricing code.

In graph state these models are stored as plain dicts
(`model.model_dump(mode="json")`) and rebuilt with `Model.model_validate(d)`.
See planner/graph/state.py for why.
"""

from datetime import date
from typing import ClassVar, Literal, Self, get_args

from pydantic import BaseModel, Field, ValidationInfo, field_validator

# --- Fixed tag vocabulary ----------------------------------------------------
# The profiler may only use these tags, and destinations.csv will tag places
# with the same words, so a preference can always be matched to a destination.
# Each vocabulary is written once, as a Literal type (so Pydantic and the JSON
# schema sent to the LLM both know the allowed values), and the tuple of values
# is derived from it with get_args() for prompts and lookups.
Setting = Literal["beach", "hills", "forest", "desert", "backwaters", "heritage", "city"]
Mood = Literal["calm", "adventurous", "romantic", "social", "spiritual"]
Interest = Literal[
    "food", "trekking", "wildlife", "temples", "history",
    "nightlife", "water sports", "photography", "wellness",
]
Avoid = Literal["crowds", "long drives", "heat", "cold", "rain"]
Pace = Literal["slow", "balanced", "packed"]
Mode = Literal["flight", "train", "bus"]

SETTINGS: tuple[str, ...] = get_args(Setting)
MOODS: tuple[str, ...] = get_args(Mood)
INTERESTS: tuple[str, ...] = get_args(Interest)
AVOIDS: tuple[str, ...] = get_args(Avoid)
MODES: tuple[str, ...] = get_args(Mode)


class Extracted(BaseModel):
    """Shared behaviour for models the LLM fills in a little at a time."""

    # Which vocabulary each tag-list field uses. Subclasses fill this in.
    # ClassVar tells Pydantic this is a class-level constant, not a field.
    VOCAB: ClassVar[dict[str, tuple[str, ...]]] = {}

    @field_validator("*", mode="before")
    @classmethod
    def _keep_known_tags(cls, value, info: ValidationInfo):
        """Clean tag lists *before* type checking: lower-case, trim, de-duplicate,
        and drop any tag that isn't in the vocabulary.

        Why drop instead of reject: with a strict Literal, one invented tag
        ("seaside" instead of "beach") would fail the whole LLM answer and lose
        every good value in it. Dropping keeps the good values; the profiler
        simply asks again about whatever is still missing.
        """
        allowed = cls.VOCAB.get(info.field_name)
        if allowed is None:
            return value  # not a tag-list field: leave it to normal validation
        if value is None:
            return []
        if isinstance(value, str):
            value = [value]  # LLMs sometimes send one tag instead of a list
        cleaned: list[str] = []
        for item in value:
            tag = item.strip().lower() if isinstance(item, str) else None
            if tag in allowed and tag not in cleaned:
                cleaned.append(tag)
        return cleaned

    def merged(self, new: Self) -> Self:
        """Return a copy of self updated with every value `new` actually provides.

        Rule: a field in `new` replaces the old value only if it says something,
        i.e. it is not None and not an empty list. So an LLM answer that
        only mentions the budget can't wipe out the dates found earlier.

        Lists are *replaced*, not added to. The extracting node shows the LLM
        the current values and asks for the full updated list, which is what
        lets a user take something back ("actually, no beaches").
        """
        updates = {name: value for name, value in new if value not in (None, [])}
        return self.model_copy(update=updates)


class Preferences(Extracted):
    """What kind of trip the user wants. Filled by the profiler node."""

    VOCAB = {"settings": SETTINGS, "moods": MOODS, "interests": INTERESTS, "avoid": AVOIDS}

    settings: list[Setting] = []
    moods: list[Mood] = []
    interests: list[Interest] = []
    avoid: list[Avoid] = []
    pace: Pace | None = None

    def is_complete(self) -> bool:
        """Enough to score destinations. `avoid` is optional: many people avoid nothing."""
        return bool(self.settings and self.moods and self.interests and self.pace)


class TripInputs(Extracted):
    """The practical facts of the trip. Filled by the constraints node.

    Every field starts as None, meaning "not asked or not answered yet", which
    is different from an answer such as 0 children. `missing()` relies on that.
    The limits (`ge`/`le`) are enforced here rather than trusted to the prompt,
    because the LLM can't be relied on to respect them.
    """

    VOCAB = {"modes": MODES}

    origin_city: str | None = None
    start_date: date | None = None
    nights: int | None = Field(None, ge=1, le=14)
    adults: int | None = Field(None, ge=1, le=6)
    # LLD.md has `children: int = 0`. It is None here instead, so that "not said
    # yet" is different from "no children": with a 0 default, merged() could
    # never tell an answer of 0 from a field the LLM left blank.
    children: int | None = Field(None, ge=0, le=4)
    budget_inr: int | None = Field(None, gt=0)  # total for the whole group
    modes: list[Mode] = []

    # Past start dates are not rejected here: "today" changes, which makes such
    # a validator hard to test. The constraints node checks that, because it
    # already puts today's date in its prompt.

    def missing(self) -> list[str]:
        """Fields still needed before destinations can be priced, in asking order.

        `children` is not listed: if nobody mentions children, assume none.
        """
        return [f for f in ("origin_city", "start_date", "nights", "adults",
                            "budget_inr", "modes") if not getattr(self, f)]

    @property
    def travellers(self) -> int:
        """Everyone travelling, for per-person costs. Unknown children count as 0."""
        return (self.adults or 0) + (self.children or 0)
