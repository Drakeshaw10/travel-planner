"""Spike: can GPT-OSS-120B on the HF router fill our Pydantic models directly?

A "spike" is a throwaway experiment that answers one question before you build
on an assumption. The profiler and constraints nodes (Phase 3, Steps 3-4) will
call `llm.with_structured_output(Preferences)`. LangChain can do that three ways,
and an OpenAI-compatible router doesn't always support all of them:

- "json_schema":      the API is given the JSON schema and constrains the output
                      to it. The most reliable, when the provider supports it.
- "function_calling": the schema is sent as a tool; the model "calls" it with
                      arguments. Widely supported.
- "json_mode":        the API only promises *some* valid JSON; the schema is only
                      described in the prompt. The weakest guarantee.

For each method this script runs a few sample conversations and records
whether the call worked, whether the result parsed into our model, what came
out, and how long it took.

Run from the project root (spends a few thousand tokens of HF credit):

    uv run python -m scripts.spike_structured_output
    uv run python -m scripts.spike_structured_output --model gemini-3.5-flash --methods json_schema

(`-m` puts the project root on the import path so `planner` can be imported;
`python scripts/spike_structured_output.py` would only see the scripts/ folder.)
"""

import argparse
import time
import tomllib
from datetime import date
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from planner.models import AVOIDS, INTERESTS, MOODS, SETTINGS, Preferences, TripInputs

METHODS = ("json_schema", "function_calling", "json_mode")

# Each case: (model to fill, conversation, what a correct answer must contain).
CASES = [
    (
        Preferences,
        "I want somewhere quiet by the sea, I just want to relax and eat good seafood. "
        "Nothing rushed please, and I really can't stand crowds.",
        lambda p: "beach" in p.settings and "calm" in p.moods and "food" in p.interests
        and p.pace == "slow" and "crowds" in p.avoid,
    ),
    (
        Preferences,
        "Honestly I'm up for anything adventurous: treks, wildlife, the works. Pack the days.",
        lambda p: "adventurous" in p.moods and "trekking" in p.interests and p.pace == "packed",
    ),
    (
        TripInputs,
        "We're two adults and one kid from Pune, leaving on 2026-11-20 for 4 nights. "
        "Budget is 60k total, and we'd take a train or a bus, no flights.",
        lambda t: t.origin_city and t.origin_city.lower() == "pune" and t.adults == 2
        and t.children == 1 and t.nights == 4 and t.start_date == date(2026, 11, 20)
        and t.budget_inr == 60000 and set(t.modes) == {"train", "bus"},
    ),
]


def system_prompt(model) -> str:
    """The kind of instructions the real nodes will use: fixed vocabulary + rules."""
    if model is Preferences:
        return (
            "Extract the user's travel preferences. Use only these tags.\n"
            f"settings: {', '.join(SETTINGS)}\nmoods: {', '.join(MOODS)}\n"
            f"interests: {', '.join(INTERESTS)}\navoid: {', '.join(AVOIDS)}\n"
            "pace: slow, balanced or packed.\n"
            "Leave a field empty or null if the user hasn't said anything about it. "
            "Respond in JSON."  # json_mode requires the word JSON in the prompt
        )
    return (
        f"Today is {date.today().isoformat()}. Extract the trip details the user gave. "
        "budget_inr is the total for the whole group in rupees (60k = 60000). "
        "Leave a field null if the user hasn't said it. Respond in JSON."
    )


def make_llm(model: str | None = None) -> ChatOpenAI:
    # Read the secrets file directly: this script runs outside Streamlit, so
    # st.secrets (and planner.llm.get_llm) isn't the right tool here.
    secrets = tomllib.loads(Path(".streamlit/secrets.toml").read_text(encoding="utf-8"))
    return ChatOpenAI(
        base_url=secrets["LLM_BASE_URL"], api_key=secrets["LLM_API_KEY"],
        model=model or secrets["LLM_MODEL"], temperature=0, timeout=60, max_retries=1,
    )


def run(model_name: str | None, methods: list[str], pause: float):
    llm = make_llm(model_name)
    print("model:", llm.model_name)
    results = {m: 0 for m in methods}
    for method in methods:
        print(f"\n=== method={method}")
        for model, text, is_correct in CASES:
            # include_raw=True returns {"raw", "parsed", "parsing_error"} instead
            # of raising, so we can see *why* something failed.
            time.sleep(pause)  # free tiers limit requests per minute
            runnable = llm.with_structured_output(model, method=method, include_raw=True)
            started = time.perf_counter()
            try:
                out = runnable.invoke([SystemMessage(system_prompt(model)), HumanMessage(text)])
            except Exception as exc:  # the API itself refused the request
                print(f"  {model.__name__:12} API ERROR {type(exc).__name__}: {str(exc)[:200]}")
                continue
            seconds = time.perf_counter() - started
            parsed, error = out["parsed"], out["parsing_error"]
            if error or parsed is None:
                print(f"  {model.__name__:12} PARSE FAIL {seconds:4.1f}s: {str(error)[:200]}")
                continue
            ok = bool(is_correct(parsed))
            results[method] += ok
            print(f"  {model.__name__:12} {'CORRECT' if ok else 'WRONG  '} {seconds:4.1f}s "
                  f"{parsed.model_dump(mode='json', exclude_defaults=True)}")
    print("\n=== summary: correct answers per method (out of", len(CASES), ")")
    for method, score in results.items():
        print(f"  {method:17} {score}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", help="override LLM_MODEL from secrets")
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--pause", type=float, default=0, help="seconds to wait before each call")
    args = parser.parse_args()
    run(args.model, args.methods, args.pause)
