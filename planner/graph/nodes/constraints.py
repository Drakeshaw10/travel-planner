"""The constraints node: collects the practical facts of the trip as `TripInputs`.

It runs after every user message while `phase == "constraints"`, i.e. once the
profiler knows what kind of trip the user wants. Like the profiler it never
talks to the user: it updates `state["trip"]` and decides when the trip is
fully described. The `chat` node runs next and asks for whatever is missing.
"""

import json
import logging
from collections.abc import Callable
from datetime import date

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage

from planner.graph.nodes.chat import is_edit_turn
from planner.graph.nodes.extraction import extract
from planner.models import TripInputs

logger = logging.getLogger(__name__)

# Same window as the profiler (LLD.md: "last 10 messages"). Facts found earlier
# are already in `trip`, which goes into the prompt.
RECENT_MESSAGES = 10

SYSTEM_PROMPT = """\
You extract trip details from a conversation with a traveller in India.

Today is {today} ({weekday}). Resolve relative dates ("next Friday", "this
Diwali weekend", "20th Nov") to a calendar date. If no year is given, pick the
year that puts the date closest to today, even if that date has already passed:
report what the user said, don't correct it.

Fields:
- origin_city: the Indian city they travel from.
- start_date: the day they leave (YYYY-MM-DD).
- nights: number of nights away (a "3-day trip" is 2 nights).
- adults: people aged 12 or over; children: under 12.
- budget_inr: the TOTAL budget for the whole group in rupees, as a whole number.
  "60k" = 60000, "1.5 lakh" = 150000. If they give a per-person budget,
  multiply by the number of travellers.
- modes: how they are willing to travel: flight, train and/or bus.
  "Anything is fine" means all three.

Trip details already known:
{current}

Return the full, updated trip details:
- Keep known values unless the user has changed them.
- Leave a field null (or modes empty) if the user hasn't said it. Never guess.
"""


def build_prompt(current: TripInputs, today: date) -> str:
    """Fill the prompt with today's date and the known trip details.

    Why today's date: the model has no clock. Without it, "next Friday" or
    "20th Nov" can't be turned into a real date, and the model would guess a
    year from its training data.
    """
    return SYSTEM_PROMPT.format(
        today=today.isoformat(),
        weekday=today.strftime("%A"),
        current=json.dumps(current.model_dump(mode="json"), indent=2),
    )


def drop_past_date(found: TripInputs, today: date) -> tuple[TripInputs, list[str]]:
    """Discard a start date that is already in the past, and say why.

    The prompt tells the model to report the date the user meant, even a past
    one ("1st October" said on 8 October is 2026-10-01, not 2027-10-01). That
    way a mistake shows up here instead of silently moving the trip a year
    ahead. A trip can't start yesterday, so the value is dropped.

    Returns the cleaned answer plus a list of problems for the user. Without
    the problem message, the chat node couldn't tell the user why their date
    was ignored: either it asks for a date again with no explanation, or a
    previously agreed date stays in place and the request looks unheard.

    This check lives here, not in TripInputs, because it needs today's date,
    and a model validator that reads the clock is hard to test.
    """
    if found.start_date is not None and found.start_date < today:
        logger.info("Dropping past start_date %s (today is %s)", found.start_date, today)
        problem = (f"The start date {found.start_date:%d %B %Y} has already passed "
                   f"(today is {today:%d %B %Y}).")
        return found.model_copy(update={"start_date": None}), [problem]
    return found, []


def make_constraints(llm: BaseChatModel, today: Callable[[], date] = date.today):
    """Build the constraints node around a given model.

    `today` is passed in for the same reason the model is: tests can fix "today"
    to a known date (dependency injection of the clock). Production uses the
    real `date.today`. It is called on every run, not once at startup, because
    the app process can stay up across midnight.
    """
    # json_schema: chosen by the Step 2 spike; include_raw for extract()'s retry.
    extractor = llm.with_structured_output(TripInputs, method="json_schema", include_raw=True)

    def constraints(state) -> dict:
        now = today()
        current = TripInputs.model_validate(state.get("trip", {}))
        messages = [SystemMessage(build_prompt(current, now)), *state["messages"][-RECENT_MESSAGES:]]

        found = extract(extractor, messages, "constraints")
        problems: list[str] = []
        if found:
            found, problems = drop_past_date(found, now)
        updated = current.merged(found) if found else current

        # trip_problems is rewritten on every run, so a problem from an
        # earlier turn never lingers once the user has fixed it.
        update = {"trip": updated.model_dump(mode="json"), "trip_problems": problems}
        if not updated.missing() and not problems and not is_edit_turn(state):
            # Everything needed to price destinations is known and nothing the
            # user just said was rejected: move on to scoring and the shortlist
            # (`after_constraints` routes on this). With an open problem we
            # stay here, so the user can answer it before anything is priced
            # with values they were trying to change. On the turn the user
            # clicked "Change trip details" the trip is complete too, but we
            # stay so chat can ask what to change; the next message decides.
            update["phase"] = "selection"
        return update

    return constraints
