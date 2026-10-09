"""Turn LLM provider errors into messages a user can act on.

Without this, every failure showed "Something went wrong" and a Retry button,
even when Retry couldn't work for hours (a free tier's daily quota used up).
This module looks at the exception and says what happened, and when trying
again makes sense. The full exception is still logged by app.py for the
developer; only the friendly text reaches the screen.
"""

import re
from datetime import datetime, timedelta, timezone

import openai

# The app is for travellers in India, so times are shown in IST (fixed UTC+5:30,
# no daylight saving, so no time-zone database is needed).
IST = timezone(timedelta(hours=5, minutes=30), "IST")

GENERIC = "Something went wrong while I was replying."
PER_MINUTE = ("I'm getting a lot of requests right now. "
              "Please wait a minute, then press Retry. Your trip is saved.")
UNAVAILABLE = ("The planner's AI service isn't available at the moment. "
               "Your trip is saved, so please try again later.")
DAILY_QUOTA = ("The planner has used up today's free AI allowance. {when} "
               "Your trip is saved: come back then and press Retry.")


def _status_error(exc: BaseException) -> openai.APIStatusError | None:
    """Find the provider's HTTP error in the exception chain, if there is one.

    Libraries often wrap errors (`raise X from e`), so the useful exception may
    sit in `__cause__` or `__context__` rather than at the top.
    """
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        if isinstance(exc, openai.APIStatusError):
            return exc
        exc = exc.__cause__ or exc.__context__
    return None


def _retry_after(text: str) -> timedelta | None:
    """Read how long to wait from the provider's message, if it says.

    Gemini includes both `'retryDelay': '59450s'` and "Please retry in
    16h30m50.8s". The first is simpler and more reliable, so it is tried first.
    """
    if m := re.search(r"retryDelay'?\"?\s*:\s*'?\"?(\d+)s", text):
        return timedelta(seconds=int(m.group(1)))
    if m := re.search(r"retry in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", text):
        hours, minutes, seconds = (float(g) if g else 0 for g in m.groups())
        if hours or minutes or seconds:
            return timedelta(hours=hours, minutes=minutes, seconds=seconds)
    return None


def _when(wait: timedelta | None, now: datetime) -> str:
    if wait is None:
        return "It resets once a day."
    back = (now + wait).astimezone(IST)
    hours, rest = divmod(int(wait.total_seconds()), 3600)
    minutes = rest // 60
    in_text = f"{hours} h {minutes} min" if hours else f"{minutes} min"
    return f"It should be back around {back:%I:%M %p} IST (in about {in_text})."


def user_message(exc: BaseException, now: datetime | None = None) -> str:
    """The message to show the user for an exception raised during a graph run.

    `now` is injected so tests can check the reset time exactly.
    """
    error = _status_error(exc)
    if error is None:
        return GENERIC

    text = str(error)
    if error.status_code == 429:
        # Gemini names the quota that ran out, e.g.
        # GenerateRequestsPerDayPerProjectPerModel-FreeTier. A per-day quota
        # won't come back for hours; anything else is a short-term limit.
        if "PerDay" in text:
            return DAILY_QUOTA.format(when=_when(_retry_after(text), now or datetime.now(timezone.utc)))
        return PER_MINUTE
    if error.status_code in (401, 402, 403):
        # Bad or expired key, or no credits left: the user can't fix this,
        # and retrying soon won't help. The log tells the developer which.
        return UNAVAILABLE
    return GENERIC
