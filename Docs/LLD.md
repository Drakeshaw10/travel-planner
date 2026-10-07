# Low-level design

Companion docs: [hld.md](hld.md) and [architecture.md](architecture.md).

This document specifies each module, node, algorithm and table precisely enough to code from. Phases 0 to 2 already match it; later phases fill in the rest.

## Module layout

Imports only point downward: `ui` calls `graph`, nodes call `tools`, tools call `cache`, and only `llm.py`, `db.py` and `cache.py` touch secrets. Files marked (Phase 2) already exist.

```text
travel-planner/
  app.py                    # (Phase 2) trip id, history, streaming, chat input
  ui/
    chat.py                 # render_history(), stream_reply()
    shortlist.py            # destination cards with a Pick button each
    itinerary.py            # day-by-day view and cost table
    debug.py                # sidebar state inspector, dev only
  planner/
    llm.py                  # (Phase 2) get_llm(): cached ChatOpenAI on the HF router
    db.py                   # (Phase 2) get_checkpointer(): pool + PostgresSaver
    cache.py                # cached_fetch(), quota_left(), log_usage()
    models.py               # Pydantic: Preferences, TripInputs, Candidate, PricedItem
    pricing.py              # distance_km(), cost_floor(), daily_spend_items()
    scoring.py              # score_destination(), rank()
    graph/
      state.py              # (Phase 2) TravelState
      build.py              # (Phase 2) build_graph(llm, checkpointer)
      nodes/
        chat.py             # (Phase 2) greet, wait_for_user, chat
        orchestrator.py     # (Phase 2) route() and every other conditional edge
        profiler.py
        constraints.py
        scorer.py
        feasibility.py
        shortlist.py
        logistics.py
        experience.py
        budget.py
        writer.py
    tools/
      flights.py            # SerpApi google_flights
      hotels.py             # SerpApi google_hotels
      trains.py             # train and bus fares from the fare charts
      places.py             # OpenTripMap, then Geoapify
      weather.py            # Open-Meteo
    data/                   # destinations.csv, origins.csv, train_fares.csv,
                            # bus_fares.csv, flight_bands.csv, entry_fees.csv
  scripts/
    load_destinations.py    # CSV to Neon, run after editing the CSVs
  tests/
```

`scoring.py` and `pricing.py` are plain Python with no LLM or network, so the numbers that matter are unit-tested on their own.

## State schema

State stores plain dicts made with `model_dump(mode="json")`, and nodes rebuild the Pydantic model with `model_validate()` when they read it. This keeps every checkpoint plain JSON, so a model change never breaks a saved trip.

```python
# planner/models.py
class Preferences(BaseModel):
    settings: list[str] = []      # "beach", "hills", "forest", "heritage", "city"
    moods: list[str] = []         # "calm", "adventurous", "romantic", "social"
    interests: list[str] = []     # "food", "trekking", "wildlife", "temples"
    avoid: list[str] = []         # "crowds", "long drives", "heat"
    pace: Literal["slow", "balanced", "packed"] | None = None

    def is_complete(self) -> bool:
        return bool(self.settings and self.moods and self.interests and self.pace)

class TripInputs(BaseModel):
    origin_city: str | None = None
    start_date: date | None = None
    nights: int | None = Field(None, ge=1, le=14)
    adults: int | None = Field(None, ge=1, le=6)
    children: int = Field(0, ge=0, le=4)
    budget_inr: int | None = Field(None, gt=0)      # total for the whole group
    modes: list[Literal["flight", "train", "bus"]] = []

    def missing(self) -> list[str]:
        return [f for f in ("origin_city", "start_date", "nights", "adults",
                            "budget_inr", "modes") if not getattr(self, f)]

class Candidate(BaseModel):
    dest_id: str
    name: str
    score: float
    floor_inr: int                # cheapest plausible total
    typical_inr: int              # mid-range total
    reason: str = ""              # one line, written by the shortlist node

class PricedItem(BaseModel):
    kind: Literal["transport", "hotel", "activity", "food", "local"]
    label: str
    day: int | None = None        # None = whole trip
    amount_inr: int
    source: str                   # "serpapi", "fare_chart", "entry_fees", "estimate"
    fetched_at: datetime | None = None
    is_estimate: bool
    url: str | None = None
    options: list[dict] = []      # cheaper alternatives kept for the budget loop
```

```python
# planner/graph/state.py
class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    phase: NotRequired[Literal["discovery", "constraints", "selection", "planning", "done"]]
    user_turns: NotRequired[int]               # caps discovery at 6 turns
    preferences: NotRequired[dict]             # Preferences
    trip: NotRequired[dict]                    # TripInputs
    candidates: NotRequired[list[dict]]        # Candidate, best first
    selected: NotRequired[str]                 # dest_id
    transport: NotRequired[list[dict]]         # PricedItem, written by logistics
    stays: NotRequired[list[dict]]             # PricedItem, written by logistics
    activities: NotRequired[list[dict]]        # PricedItem, written by experience
    weather: NotRequired[list[dict]]           # one row per day
    total_inr: NotRequired[int]
    budget_attempts: NotRequired[int]
    budget_target: NotRequired[Literal["logistics", "experience"]]
    budget_feedback: NotRequired[str]
    validation_status: NotRequired[Literal["ok", "best_effort"]]
    itinerary_md: NotRequired[str]
```

Logistics and experience run in parallel but write different keys, so no reducer is needed beyond `add_messages`.

## Graph nodes

Thirteen nodes; only `chat` and `writer` stream text to the user, so `app.py` filters the message stream on those two names.

| Node | Reads | Writes | Calls | LLM use |
| --- | --- | --- | --- | --- |
| `greet` | nothing | greeting message, `phase=discovery` | none | none |
| `wait_for_user` | nothing | the user's `HumanMessage`, `user_turns + 1` | `interrupt("waiting_for_user")` | none |
| `profiler` | last 10 messages, `preferences` | merged `preferences`; `phase=constraints` once complete or after 6 turns | LLM | `with_structured_output(Preferences)` |
| `constraints` | last 10 messages, `trip` | merged `trip`; `phase=selection` once nothing is missing | LLM | `with_structured_output(TripInputs)` |
| `chat` | `phase`, `preferences`, `trip.missing()` | the next question as an `AIMessage` | LLM | streamed reply, one question at a time |
| `scorer` | `preferences`, `trip.start_date`, `destinations` table | top 10 `candidates` | `scoring.rank()` | none |
| `feasibility` | `candidates`, `trip`, `origins` table | top 5 that fit the budget, each with `floor_inr` and `typical_inr` | `pricing.cost_floor()` | none |
| `shortlist` | `candidates`, `preferences` | `reason` per candidate | LLM | one structured call for all reasons |
| `pick` | `candidates` | `selected`, `phase=planning` | `interrupt({"type": "shortlist", "candidates": [...]})` | none |
| `logistics` | `trip`, `selected`, `budget_feedback` | `transport`, `stays` | flights, hotels, trains tools | none |
| `experience` | `selected`, `trip`, `preferences`, `budget_feedback` | `activities`, `weather` | places, weather tools, entry fees | ranks attractions against interests |
| `budget` | `transport`, `stays`, `activities`, `trip` | `total_inr`, `budget_attempts`, `budget_target`, `budget_feedback`, `validation_status` | `pricing.daily_spend_items()` | none |
| `writer` | everything above | `itinerary_md`, `phase=done` | LLM | streamed day-by-day plan; prices come from state, never from the model |

`pick` is its own node because a resumed node re-runs from its first line, which would repeat the reasons call. Its interrupt carries the candidates as data; `ui/shortlist.py` draws a card per candidate and resumes the graph with `Command(resume=dest_id)` when one is picked.

## Routing rules

All conditional edges live in `orchestrator.py` and only read state; they never call the LLM or an API, so each one is a one-line unit test.

```python
# planner/graph/nodes/orchestrator.py
def route(state) -> Literal["profiler", "constraints", "chat"]:
    """After wait_for_user."""
    match state.get("phase", "discovery"):
        case "discovery":   return "profiler"
        case "constraints": return "constraints"
        case _:             return "chat"        # "done": questions about the finished plan

def after_constraints(state) -> Literal["scorer", "chat"]:
    return "scorer" if state.get("phase") == "selection" else "chat"

def after_feasibility(state) -> Literal["shortlist", "chat"]:
    # No candidate fits: feasibility already set phase back to "constraints"
    # and chat explains the cheapest option and what to change.
    return "shortlist" if state.get("candidates") else "chat"

def after_budget(state) -> Literal["logistics", "experience", "writer"]:
    if state.get("validation_status"):            # "ok" or "best_effort"
        return "writer"
    return state["budget_target"]
```

```python
# planner/graph/build.py (edges only)
g.add_edge(START, "greet")
g.add_edge("greet", "wait_for_user")
g.add_conditional_edges("wait_for_user", route)
g.add_edge("profiler", "chat")
g.add_conditional_edges("constraints", after_constraints)
g.add_edge("chat", "wait_for_user")
g.add_edge("scorer", "feasibility")
g.add_conditional_edges("feasibility", after_feasibility)
g.add_edge("shortlist", "pick")
g.add_edge("pick", "logistics")        # these two run in parallel
g.add_edge("pick", "experience")
g.add_edge("logistics", "budget")      # two plain edges, not a list:
g.add_edge("experience", "budget")     # budget also re-runs after one side alone
g.add_conditional_edges("budget", after_budget)
g.add_edge("writer", "wait_for_user")
```

The fan-in was checked on LangGraph 1.2: after the parallel step `budget` runs once, and on a retry it runs again after `logistics` alone. A list edge, `add_edge(["logistics", "experience"], "budget")`, would wait for both and stall the retry loop.

## Discovery scoring

The LLM only turns chat into `Preferences`; ranking is a fixed weighted score in `scoring.py`, so the same answers always give the same shortlist.

```latex
\text{score} = 0.35\,S + 0.25\,M + 0.20\,I + 0.10\,T + 0.10\,C - 0.20\,A
```

| Term | Meaning | How it is computed (0 to 1) |
| --- | --- | --- |
| S | Setting match | share of the user's settings the destination has; 0.5 if the user gave none |
| M | Mood match | same rule over moods |
| I | Interest match | same rule over interests |
| T | Season fit | 1 if the start month is in `best_months`, 0.5 if a neighbouring month, else 0 |
| C | Crowd fit | `1 - (crowd_level - 1) / 4` if the user avoids crowds, else 0.5 |
| A | Avoid hits | number of the user's `avoid` tags found in the destination's tags |

```python
# planner/scoring.py
def match(wanted: list[str], has: list[str]) -> float:
    return len(set(wanted) & set(has)) / len(wanted) if wanted else 0.5

def rank(prefs: Preferences, month: int, rows: list[dict], k: int = 10) -> list[Candidate]:
    scored = [(score_destination(prefs, month, r), r) for r in rows]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [Candidate(dest_id=r["id"], name=r["name"], score=round(s, 3),
                      floor_inr=0, typical_inr=0) for s, r in scored[:k]]
```

The profiler stops asking once `Preferences.is_complete()` is true or after 6 user turns, whichever comes first. Tags are a fixed vocabulary listed in the profiler's system prompt, so the LLM cannot invent a tag the table does not use. The weights are a starting point to tune by hand in Phase 4.

## Feasibility and cost floor

A destination stays on the shortlist only if its cheapest plausible total fits the budget, and the floor uses tables only, so feasibility spends no API calls.

```latex
\text{floor} = \text{transport}_{\min} + \text{nights} \times \text{rooms} \times \text{hotel}_{\text{budget}} + (\text{nights} + 1) \times \text{travellers} \times \text{spend}_{\text{daily}}
```

| Input | Source |
| --- | --- |
| `rooms` | `ceil(adults / 2)`; children share |
| `travellers` | `adults + children` |
| `hotel_budget`, `hotel_mid` | price bands per room per night in `destinations` |
| `spend_daily` | food and local transport per person per day in `destinations` |
| Distance | straight-line distance between `origins` and `destinations` coordinates, times 1.3 for road and rail |
| `transport_min` | cheapest round trip over the allowed modes: train and bus from the fare charts by distance, flight from `flight_bands.csv` by distance band |

```python
# planner/pricing.py
def cost_floor(trip: TripInputs, origin: dict, dest: dict, band: str = "budget") -> int:
    km = distance_km(origin, dest)
    travellers = trip.adults + trip.children
    rooms = math.ceil(trip.adults / 2)
    transport = min(round_trip_estimate(mode, km, travellers) for mode in trip.modes)
    stay = trip.nights * rooms * dest[f"hotel_{band}_inr"]
    spend = (trip.nights + 1) * travellers * dest["daily_spend_inr"]
    return transport + stay + spend
```

`typical_inr` is the same sum with the mid hotel band, and the shortlist shows the range floor to typical. If no candidate fits, feasibility sets `phase` back to `constraints` and the chat node names the cheapest floor found, then suggests a bigger budget, fewer nights or another travel mode.

## Tools and cache

Every tool returns typed `PricedItem`s or plain rows and gets its data through `cached_fetch()`, which is the only code that knows about the 72-hour rule and the SerpApi quota.

| Tool | Signature | Provider and endpoint | Cache age | Fallback |
| --- | --- | --- | --- | --- |
| Flights | `search_flights(origin_iata, dest_iata, out_date, ret_date, adults) -> list[PricedItem]` | SerpApi `engine=google_flights`, `type=1` round trip, `currency=INR` | 72 h | `flight_bands.csv` estimate |
| Hotels | `search_hotels(dest_name, check_in, check_out, adults) -> list[PricedItem]` | SerpApi `engine=google_hotels`, `currency=INR` | 72 h | `destinations` price bands |
| Trains, buses | `estimate_ground(km, mode, travellers) -> PricedItem` | fare charts in `planner/data/` | none needed | always an estimate |
| Attractions | `find_attractions(lat, lon, interests, limit=20) -> list[Place]` | OpenTripMap radius search | 72 h | Geoapify Places |
| Entry fees | `entry_fee(place_name) -> PricedItem or None` | `entry_fees.csv` | none needed | free, or marked unknown |
| Weather | `get_weather(lat, lon, start, nights) -> list[DayWeather]` | Open-Meteo forecast, up to 16 days ahead | 6 h | same dates last year from the Open-Meteo archive, labelled typical |

```python
# planner/cache.py
MAX_AGE = {"serpapi": timedelta(hours=72), "opentripmap": timedelta(hours=72),
           "geoapify": timedelta(hours=72), "open-meteo": timedelta(hours=6)}
SERPAPI_MONTHLY = 250
SERPAPI_PER_TRIP = 3

def cached_fetch(provider: str, params: dict, fetch: Callable[[], dict],
                 thread_id: str | None = None) -> tuple[dict, datetime]:
    key = sha256(f"{provider}:{json.dumps(params, sort_keys=True)}".encode()).hexdigest()
    row = select_cache(key)                                # response, fetched_at
    if row and now() - row.fetched_at < MAX_AGE[provider]:
        return row.response, row.fetched_at                # fresh hit, no API call
    if provider == "serpapi" and (quota_left() <= 0 or trip_calls(thread_id) >= SERPAPI_PER_TRIP):
        raise QuotaExhausted(provider)                     # caller falls back to an estimate
    data = fetch()                                         # 15 s timeout, 1 retry on 5xx or timeout
    upsert_cache(key, provider, params, data)
    log_usage(provider, thread_id, calls=1)
    return data, now()
```

Data older than its cache age is never shown, even when the quota is gone; the tool returns an estimate marked `is_estimate=True` instead. Each `PricedItem` keeps `fetched_at`, so the itinerary can say how old every price is.

## Budget controller

The budget node adds up every item in Python and, when the plan is over, sends it back to whichever side costs more, up to 3 rounds. Retries reuse the options already fetched, so a retry costs no API calls.

```python
# planner/graph/nodes/budget.py
MAX_ATTEMPTS = 3

def budget(state: TravelState) -> dict:
    trip = TripInputs.model_validate(state["trip"])
    items = [PricedItem.model_validate(i) for i in
             state["transport"] + state["stays"] + state["activities"]]
    items += daily_spend_items(trip, state["selected"])      # food and local, estimates
    total = sum(i.amount_inr for i in items)
    if total <= trip.budget_inr:
        return {"total_inr": total, "validation_status": "ok"}
    attempts = state.get("budget_attempts", 0) + 1
    if attempts > MAX_ATTEMPTS:
        return {"total_inr": total, "validation_status": "best_effort"}
    over = total - trip.budget_inr
    logistics_cost = sum(i.amount_inr for i in items if i.kind in ("transport", "hotel"))
    activity_cost = sum(i.amount_inr for i in items if i.kind == "activity")
    target = "logistics" if logistics_cost >= activity_cost else "experience"
    return {"total_inr": total, "budget_attempts": attempts, "budget_target": target,
            "budget_feedback": f"Over budget by Rs {over}. Cut at least Rs {over}."}
```

| On retry | Logistics does, in order | Experience does, in order |
| --- | --- | --- |
| 1st cut | next cheaper hotel from `options` | swap the priciest paid activity for a free one |
| 2nd cut | train or bus instead of flight, if the user allowed it | drop paid activities with the lowest interest match |
| 3rd cut | lowest hotel band | keep only free activities |

A `best_effort` plan is still written, with a line at the top saying how far over budget it is and which cut would close the gap. Food and local transport are never cut; they come from the destination's daily spend and are labelled estimates.

## Database schema

Four tables are yours; the checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) are created and migrated by `PostgresSaver.setup()`, so never edit them by hand. Run this once on each Neon branch, `dev` and `main`.

```sql
create table if not exists destinations (
  id                text primary key,           -- 'gokarna'
  name              text not null,
  state             text not null,
  lat               double precision not null,
  lon               double precision not null,
  settings          text[] not null,            -- {beach,hills}
  moods             text[] not null,
  interests         text[] not null,
  tags_avoid        text[] not null default '{}', -- {crowds,heat} the place is known for
  best_months       smallint[] not null,        -- {10,11,12,1,2}
  crowd_level       smallint not null check (crowd_level between 1 and 5),
  airport_iata      text,
  station_code      text,
  hotel_budget_inr  int not null,               -- per room per night
  hotel_mid_inr     int not null,
  hotel_upscale_inr int not null,
  daily_spend_inr   int not null,               -- food + local transport, per person per day
  updated_on        date not null
);

create table if not exists origins (
  city          text primary key,
  state         text not null,
  lat           double precision not null,
  lon           double precision not null,
  airport_iata  text,
  station_code  text
);

create table if not exists api_cache (
  key         text primary key,                 -- sha256 of provider + params
  provider    text not null,
  params      jsonb not null,
  response    jsonb not null,
  fetched_at  timestamptz not null default now()
);
create index if not exists api_cache_age on api_cache (fetched_at);

create table if not exists usage (
  id         bigserial primary key,
  at         timestamptz not null default now(),
  provider   text not null,                     -- 'serpapi', 'hf'
  thread_id  text,                              -- the trip id, when known
  calls      int not null default 0,
  tokens     int not null default 0
);
create index if not exists usage_month on usage (provider, at);
```

| Query | SQL |
| --- | --- |
| SerpApi calls this month | `select coalesce(sum(calls), 0) from usage where provider = 'serpapi' and at >= date_trunc('month', now())` |
| SerpApi calls for one trip | `select coalesce(sum(calls), 0) from usage where provider = 'serpapi' and thread_id = %s` |
| Clean old cache rows (on app start) | `delete from api_cache where fetched_at < now() - interval '7 days'` |

`scripts/load_destinations.py` upserts `destinations.csv` and `origins.csv` into these tables, so the CSVs in git stay the source of truth.

## Config, errors, limits and testing

All settings come from `st.secrets`; a failure in any node leaves the last checkpoint intact, so the user's Retry button (built in Phase 2) always resumes where it stopped.

**Secrets** (`.streamlit/secrets.toml` locally, app Settings on Streamlit Cloud)

| Key | Used by | Added in |
| --- | --- | --- |
| `HF_TOKEN`, `LLM_BASE_URL`, `LLM_MODEL` | `llm.py` | Phase 1 |
| `DATABASE_URL` | `db.py`, `cache.py` | Phase 2 |
| `SERPAPI_KEY` | `tools/flights.py`, `tools/hotels.py` | Phase 6 |
| `OPENTRIPMAP_KEY`, `GEOAPIFY_KEY` | `tools/places.py` | Phase 6 |

**Limits**

| Limit | Value | Where |
| --- | --- | --- |
| Discovery turns | 6 | `profiler` |
| Nights, adults, children | 1 to 14, 1 to 6, 0 to 4 | `TripInputs` |
| Shortlist size | 5 | `feasibility` |
| Budget rounds | 3 | `budget` |
| SerpApi calls | 3 per trip, 250 per month | `cache.py` |
| HTTP timeout | 15 s, 1 retry | `cached_fetch()` |
| LLM | `timeout=60`, `max_retries=2`, last 20 messages sent | `llm.py`, each node |
| LLM token logging | `stream_usage=True`, tokens written to `usage` | `llm.py` |

**Errors**

| What fails | What the user sees | How |
| --- | --- | --- |
| LLM call times out or errors | "Something went wrong" and a Retry button | node raises, checkpoint unchanged (Phase 2 path) |
| Structured output does not parse | the same question, rephrased | retry once with the parse error added, then keep old values |
| SerpApi quota used up or request fails | prices marked as estimates | `QuotaExhausted` or HTTP error, then table fallback |
| OpenTripMap fails | nothing different | Geoapify instead |
| Both attraction APIs fail | a day plan without named places, with a note | `activities` left empty, writer says why |
| Trip starts more than 16 days out | weather labelled typical | Open-Meteo archive for last year's dates |
| No destination fits the budget | the cheapest floor and three ways to fix it | `feasibility` sends the trip back to constraints |
| Neon asleep or connection dropped | a short pause on the first click | pool `check_connection` reconnects |

**Testing**

| Level | What | Tools |
| --- | --- | --- |
| Unit | `scoring.py`, `pricing.py`, `budget`, every routing function | pytest, no network |
| Tools | each tool against saved JSON responses in `tests/fixtures/` | pytest with `monkeypatch` on the fetch function |
| Graph | full runs with a scripted model, resumes, the budget loop | `InMemorySaver`, LangChain `GenericFakeChatModel` |
| UI | chat input, shortlist cards, Retry button | Streamlit `AppTest`, as in Phase 2 |
| End to end | one real trip on the Neon `dev` branch before each deploy | manual, `uv run streamlit run app.py` |
