# Worklog

A running record of every piece of work done on the Moody Trip Planner, newest entry last. Each entry says what changed, why, how it was verified, and what is left open, in enough detail that someone new can pick up where it stopped.

Companion docs: [Architecture.md](Architecture.md), [HLD.md](HLD.md), [LLD.md](LLD.md).

## How to add an entry

- One entry per working session or phase step, headed `## YYYY-MM-DD: <short title>`.
- Use these sub-headings, and write "None" rather than dropping one:
  - **Goal**: what the session set out to do.
  - **Changes**: every file added, changed or deleted, with what changed inside it.
  - **Decisions**: choices made and why, especially where they differ from the design docs.
  - **Verification**: the commands run and their real results, failures included.
  - **Issues found**: bugs, doc gaps or risks found, each with a status (open, fixed, wontfix).
  - **Next steps**: what the next session should do first.
- Update the **Current status** and **Open issues** sections below whenever an entry changes them.
- Never put secret values in this file; name the key only.

## Current status

_Last updated: 2026-10-07_

| Item | State |
| --- | --- |
| Phase | Phase 1 (streaming chat page) **complete** and verified (tests, live model call, server boot); committed as "Phase 1: streaming chat page" (see `git log`). Phase 2 not started. |
| Last commit | "Phase 1: streaming chat page" (2026-10-07); before that `bf58edf` Added HLD, LLD and architecture docs (`Docs/Architecture.md`, `HLD.md`, `LLD.md`, `Worklog.md`); before that `cd39644` Phase 0: project skeleton (2026-10-06) |
| Uncommitted | Nothing |
| Python | 3.12.15 in `.venv` (managed by uv); `requires-python >= 3.12` |
| Dev packages | pytest 9.1.1 (`[dependency-groups] dev`) |
| Key packages | langgraph 1.2.14, langgraph-checkpoint 4.2.0, langgraph-checkpoint-postgres 3.1.2, langchain-core 1.6.6, langchain-openai 1.6.7, streamlit 1.65.0, psycopg 3.3.6, psycopg-pool 3.3.3 |
| Tests | 4 tests in `tests/test_app.py`, all pass with `uv run pytest` (5.6 s) |
| Secrets present locally | `HF_TOKEN`, `LLM_MODEL`, `LLM_BASE_URL`, `SERPAPI_KEY`, `OPENTRIPMAP_KEY`, `GEOAPIFY_KEY`, `DATABASE_URL` in `.streamlit/secrets.toml` (gitignored, checked) |

### Phase map

The design docs name phases but don't list them all. This table is what can be read from them; rows marked "not defined" need filling in when the plan is decided.

| Phase | Scope (from the docs) | Status |
| --- | --- | --- |
| 0 | Project skeleton: uv project, Streamlit hello page | Done, committed `cd39644` |
| 1 | `planner/llm.py` on the HF router with the LLD limits; `app.py` streaming chat sending the last 20 messages; error message and retype on failure; secrets `HF_TOKEN`, `LLM_BASE_URL`, `LLM_MODEL` | Done and committed 2026-10-07 |
| 2 | LangGraph engine (`graph/state.py`, `graph/build.py`, `nodes/chat.py`, `nodes/orchestrator.py`), `planner/db.py` checkpointer on Neon, trip id in URL, Retry button, AppTest | Not started |
| 3 | Not defined in the docs | — |
| 4 | Scoring weights tuned by hand (`scoring.py`) | Not started |
| 5 | Not defined in the docs | — |
| 6 | Live tools: SerpApi flights and hotels, OpenTripMap and Geoapify places | Not started |

### Open issues

| # | Issue | Status |
| --- | --- | --- |
| 1 | `pytest` is not a project dependency, so a bare `pytest` runs the global Python 3.11 install and the AppTest times out | Fixed 2026-10-07 |
| 2 | Doc cross-links use lowercase names (`hld.md`, `lld.md`, `architecture.md`) but the files are `HLD.md`, `LLD.md`, `Architecture.md`; links break on GitHub | Open |
| 3 | `architecture.png` is linked from Architecture.md and HLD.md but does not exist | Open |
| 4 | LLD.md says Phases 0 to 2 match it and marks Phase 2 files as existing; only Phase 1 code exists | Open |
| 5 | `planner/llm.py` lacks `timeout=60`, `max_retries=2`, `stream_usage=True` from the LLD limits table | Fixed 2026-10-07; writing the token counts to `usage` waits for the Phase 2 database |
| 6 | `uv` cannot reach PyPI on this machine without `--system-certs` (TLS `UnknownIssuer`) | Open (environment) |

---

## 2026-10-06: Phase 0, project skeleton

_Reconstructed on 2026-10-07 from commit `cd39644`; not recorded at the time._

**Goal**
Set up a uv-managed Python project that deploys to Streamlit Community Cloud.

**Changes** (commit `cd39644`, author Drakeshaw10)
- `.gitignore`: ignores `.venv/`, `__pycache__/`, `.pytest_cache/`, `.streamlit/secrets.toml`.
- `pyproject.toml`: project `travelplanner` 0.1.0, `requires-python >= 3.12`; dependencies `langchain-openai>=1.6.7`, `langgraph>=1.2.14`, `langgraph-checkpoint-postgres>=3.1.2`, `psycopg[binary,pool]>=3.3.6`, `streamlit>=1.65.0`.
- `uv.lock`: lock file for the above (2231 lines).
- `requirements.txt`: 241-line pinned export, for Streamlit Community Cloud.
- `app.py`: 4 lines; title "Moody Trip Planner" and the text "Setup works".

**Decisions**
- uv for dependency management, with `requirements.txt` exported alongside for Streamlit Cloud.

**Verification**
Not recorded.

**Issues found**
None recorded.

**Next steps**
Phase 1: connect the LLM and build a streaming chat page.

---

## Before 2026-10-07: Phase 1, streaming chat page

_Reconstructed on 2026-10-07 from the uncommitted working tree; not recorded at the time._

**Goal**
A working chat page that streams replies from GPT-OSS-120B through the Hugging Face router, before any LangGraph or database work.

**Changes** (all uncommitted)
- `planner/__init__.py`: new, empty package marker.
- `planner/llm.py`: new. `get_llm()` wrapped in `@st.cache_resource` so one `ChatOpenAI` is built per server process. Reads `LLM_BASE_URL`, `HF_TOKEN`, `LLM_MODEL` from `st.secrets`; `temperature=0.7`, `streaming=True`.
- `app.py`: replaced the hello page with a chat page.
  - `SYSTEM_PROMPT`: a warm travel companion for people in India who ask one short question at a time about mood and preferences and do not suggest destinations yet.
  - `GREETING`: "Hi! Let's find you a trip without you having to pick a place first. To start: right now, would you rather hear waves or birdsong?"
  - Page config: title "Moody Trip Planner", icon 🧭, caption "Not sure where to go? Let's figure it out together."
  - History lives in `st.session_state.messages` (LangChain `AIMessage` / `HumanMessage`), seeded with the greeting.
  - Sidebar "New trip" button resets history and reruns.
  - On input: appends the `HumanMessage`, streams the reply with `st.write_stream` over `get_llm().stream([SystemMessage, *history])`, appends the `AIMessage`.
  - On any model error: removes the unanswered user message, shows "The model call failed: <error>", and stops, so the user can retype.
  - Calls `get_llm()` through the module (`from planner.llm import get_llm` at import) so the test can monkeypatch it.
- `tests/test_app.py`: new. `test_chat_round_trip` patches `planner.llm.get_llm` with `FakeListChatModel(responses=["Waves it is!"])`, runs `app.py` in `AppTest`, checks the greeting starts with "Hi!", sends "Waves, definitely", and checks there is no exception, the last bubble is "Waves it is!", and history holds 3 messages.
- `conftest.py`: new, empty. An empty root `conftest.py` makes pytest put the project root on `sys.path`, so `import planner` works from `tests/`.
- `Docs/Architecture.md`, `Docs/HLD.md`, `Docs/LLD.md`: design docs added (see the next entry for a summary).

**Decisions**
- State is held in `st.session_state` for now. This is a deliberate Phase 1 shortcut; Phase 2 moves it to the LangGraph checkpointer on Neon, per HLD "nothing is held in Streamlit memory".

**Verification**
See the 2026-10-07 entry: the test passes in the project venv.

**Issues found**
- `llm.py` does not yet set the LLD limits (`timeout=60`, `max_retries=2`, `stream_usage=True`). Logged as open issue 5.

**Next steps**
Commit Phase 1, then start Phase 2.

---

## 2026-10-07: Design doc review, test check, worklog started

**Goal**
Read the design docs to understand the system, check the current code against them, and start this worklog.

**Changes**
- `Docs/Worklog.md`: new (this file). Holds the entry rules, current status, phase map, open issues, and entries for Phase 0, Phase 1 and this session.
- No code changed.

**What the docs specify** (summary for quick reference)
- **System**: one Streamlit app on Community Cloud. Neon Postgres is the only state store (checkpoints, `destinations`, `origins`, `api_cache`, `usage`), with `dev` and `main` branches. Outside services: Hugging Face router (GPT-OSS-120B, OpenAI-compatible), SerpApi (flights, hotels), OpenTripMap and Geoapify (attractions), Open-Meteo (weather). Train and bus fares and entry fees come from CSVs in `planner/data/`.
- **Agent graph**: 13 LangGraph nodes: `greet`, `wait_for_user`, `profiler`, `constraints`, `chat`, `scorer`, `feasibility`, `shortlist`, `pick`, `logistics`, `experience`, `budget`, `writer`. `wait_for_user` and `pick` pause with `interrupt()`; the UI resumes with `Command(resume=...)` and the trip id as `thread_id`. `logistics` and `experience` run in parallel and join `budget` through two plain edges, not a list edge, so the budget retry loop does not stall.
- **Phases of a trip**: `discovery` (profiler, up to 6 turns or until `Preferences.is_complete()`), `constraints` (origin, dates, nights, travellers, budget, modes), `selection` (score, filter by cost floor, shortlist of 5, pick), `planning` (logistics, experience, budget loop of up to 3 rounds, then `ok` or `best_effort`), `done` (writer, then questions about the plan).
- **Scoring**: `0.35 S + 0.25 M + 0.20 I + 0.10 T + 0.10 C − 0.20 A`, plain Python in `scoring.py`, no LLM.
- **Cost floor**: `transport_min + nights × rooms × hotel_budget + (nights + 1) × travellers × daily_spend`, tables only, no API calls. `rooms = ceil(adults / 2)`; distance is straight-line × 1.3.
- **Prices**: every price is a `PricedItem` with `source`, `fetched_at`, `is_estimate`; totals are added in Python, never by the LLM.
- **Cache and quota**: `cached_fetch()` is the only code that knows the 72 h rule (6 h for weather) and the SerpApi limits (250 a month, 3 per trip). Stale data is never shown; tools fall back to estimates.
- **State**: plain JSON dicts in `TravelState`, rebuilt into Pydantic models with `model_validate()` on read, so a model change never breaks a saved trip.
- **Testing**: unit tests for scoring, pricing, budget and routing; tool tests against saved JSON fixtures; graph runs with `InMemorySaver` and `GenericFakeChatModel`; UI with `AppTest`; one manual end-to-end trip on Neon `dev` before each deploy.

**Decisions**
- Worklog lives at `Docs/Worklog.md`, next to the design docs and named in the same style.
- Phase 0 and Phase 1 entries were reconstructed from git and the working tree, and are labelled as such.
- Did not add `pytest` to the project or fix the doc links in this session; both are listed as open issues for the user to approve.

**Verification**
- `uv run pytest -q` → **1 failed**: `RuntimeError: AppTest script run timed out after 3(s)`. The traceback shows `...\Python311\Lib\site-packages\streamlit\...`, so this ran the global Python 3.11 pytest, not the project venv.
- `uv run which pytest` → `C:/Users/Aarush/AppData/Local/Programs/Python/Python311/Scripts/pytest`; `uv run python -c "import pytest"` → `ModuleNotFoundError`. Confirms pytest is not installed in `.venv`.
- `uv run --with pytest python -m pytest -q` → failed to download: `invalid peer certificate: UnknownIssuer` reaching pypi.org.
- `uv run --system-certs --with pytest python -m pytest -q` → **1 passed in 10.62 s** on Python 3.12.15.
- `git check-ignore -v .streamlit/secrets.toml` → matched by `.gitignore:4`; secrets are not tracked. Only key names were read, not values.

**Issues found**
1. pytest missing from the project (open issue 1). Fix: `uv add --dev pytest --system-certs`, then always run `uv run pytest`. Status: open.
2. Lowercase doc links (open issue 2). `Architecture.md` links `hld.md` and `lld.md`; `HLD.md` links `architecture.md` and `lld.md`; `LLD.md` links `hld.md` and `architecture.md`. Windows ignores case, GitHub does not. Fix: match the real file names. Status: open.
3. `architecture.png` missing (open issue 3). Fix: export the Mermaid system view to `Docs/architecture.png`, or remove the links. Status: open.
4. LLD status line is ahead of the code (open issue 4). LLD says "Phases 0 to 2 already match it" and its module layout marks `db.py`, `graph/state.py`, `graph/build.py`, `nodes/chat.py`, `nodes/orchestrator.py` as existing; none exist yet. The layout also roots at `travel-planner/` and lists a `ui/` package, while the repo is `travelPlanner/` with no `ui/` yet. Status: open; fix as Phase 2 lands.
5. `llm.py` missing LLD limits (open issue 5). Status: open; natural to fix in Phase 2 alongside token logging to `usage`.
6. uv needs `--system-certs` on this machine (open issue 6), probably antivirus or proxy TLS inspection. Setting `UV_SYSTEM_CERTS=true` in the user environment avoids passing the flag each time. Status: open, environment only.

Design notes to keep in mind when building (not bugs yet):
- `route()` sends `selection` and `planning` phases to `chat`. That is fine as long as the user can only type while the graph waits at `wait_for_user`, but a message typed while `pick` is waiting resumes `pick`, not `wait_for_user`. The UI should hide the chat input, or treat text as "none of these", while the shortlist is showing.
- `budget` calls `daily_spend_items(trip, state["selected"])` with a destination id; the function will need to look up the destination row itself.
- `pyproject.toml` has no HTTP client (`httpx` or `requests`) or explicit `pydantic` yet; the tools layer in Phase 6 will need one.

**Next steps**
1. Approve and apply the fixes for open issues 1 to 3.
2. Commit Phase 1 (`app.py`, `planner/`, `tests/`, `conftest.py`, `Docs/`).
3. Start Phase 2: `planner/graph/state.py`, `nodes/chat.py` (`greet`, `wait_for_user`, `chat`), `nodes/orchestrator.py`, `graph/build.py`, `planner/db.py` with `PostgresSaver` on the Neon `dev` branch, trip id in `?trip=`, Retry button, and AppTest coverage.

---

## 2026-10-07: Phase 1 completed

**Goal**
Finish Phase 1 before starting Phase 2: bring `planner/llm.py` and `app.py` in line with the LLD.md limits, make the test suite run in the project's own environment, cover the error path, and check the app against the real model.

**Changes**
- `pyproject.toml`: new `[dependency-groups]` table with `dev = ["pytest>=9.1.1"]`, added by `uv add --system-certs --dev pytest`. Runtime dependencies unchanged.
- `uv.lock`: +60 lines for pytest 9.1.1 and its dependencies (iniconfig, pluggy, pygments, and others).
- `requirements.txt`: unchanged. pytest is a dev-only dependency, and Streamlit Cloud doesn't need it.
- `planner/llm.py`:
  - New constant `MAX_HISTORY = 20`, the "last 20 messages sent" limit from LLD.md.
  - `ChatOpenAI` now also sets `timeout=60`, `max_retries=2` and `stream_usage=True`. Existing settings are unchanged: `base_url`, `api_key`, `model` from `st.secrets`, `temperature=0.7`, `streaming=True`.
- `app.py`:
  - Imports `MAX_HISTORY` along with `get_llm`.
  - The model now gets `[SystemMessage(SYSTEM_PROMPT), *messages[-MAX_HISTORY:]]` instead of the whole history. The full history still stays in `st.session_state.messages` and is all shown on screen.
- `tests/test_app.py`, rewritten from 1 test to 4:
  - Shared `APP = "../app.py"` and `TIMEOUT = 30`, passed to `AppTest.from_file(..., default_timeout=TIMEOUT)`. The first script run imports LangChain, which can take longer than AppTest's 3 s default (the failure seen earlier).
  - `RecordingModel`: a `FakeListChatModel` that saves the messages from each `_stream` call. `FailingModel`: a `FakeListChatModel` whose `_stream` raises `TimeoutError`.
  - `test_chat_round_trip`: unchanged behaviour, now with the longer timeout.
  - `test_model_error_drops_message_and_allows_retry`: if the model fails, there is no exception, the error box shows "The model call failed", and only the greeting is left in history. Retyping the same message with a working model then gives 3 messages.
  - `test_only_recent_history_is_sent`: after 12 user turns (25 messages before the last call), the model gets the system message plus exactly 20 messages, and the last one is the newest user message.
  - `test_llm_client_settings`: patches `st.secrets` with dummy values, clears the `cache_resource` cache, and checks model name, base URL, `request_timeout == 60`, `max_retries == 2`, `streaming` and `stream_usage` are on, and that a second call returns the same cached object. It clears the cache again at the end so other tests are unaffected.

**Decisions**
- Kept `stream_usage=True` now, although nothing records the counts yet. The live check below shows the HF router accepts it and sends counts on the last chunk. Writing them to the `usage` table needs `DATABASE_URL` and the tables, which are Phase 2.
- Trimmed history only in what goes to the model, not in what is stored or shown. Phase 2 moves history into the LangGraph state anyway.
- Left the doc link fixes and `architecture.png` (open issues 2 and 3) and the LLD.md status line (open issue 4) for later, as asked: Phase 1 code first.
- Committed on 2026-10-07 at the user's request, straight to `main` like the earlier commits, with the message "Phase 1: streaming chat page". This worklog was updated in the same commit, so its own hash can't appear here; run `git log --oneline` to see it.

**Verification**
- `uv run pytest -q` → **4 passed in 5.55 s**. `uv run pytest` now uses pytest from `.venv` (Python 3.12.15), not the global 3.11 copy.
- Live call: `get_llm().stream([HumanMessage("Reply with exactly: ready")])` with the real secrets → reply `'ready'`, first token after 1.26 s, usage on the last chunk `{'input_tokens': 72, 'output_tokens': 34, 'total_tokens': 106, ..., 'output_token_details': {'reasoning': 23}}`. So the router accepts `stream_usage`, and GPT-OSS-120B uses reasoning tokens that count toward output.
- Server boot: `uv run streamlit run app.py --server.headless true --server.port 8599` → `/_stcore/health` returned `ok` after 2 s, no errors or tracebacks in the log. The server was stopped afterwards.
- Not checked: a chat typed by hand in a browser. The AppTest runs and the live call cover the same code path, but the user may want one manual look at `uv run streamlit run app.py`.

**Issues found**
- Reasoning tokens: GPT-OSS-120B spent 23 of 34 output tokens on reasoning for a one-word reply. Worth watching for cost and first-token delay once replies get longer. Status: note only.
- Open issue 1 fixed; open issue 5 fixed except for logging, which waits for Phase 2.

**Next steps**
1. ~~Commit Phase 1~~ Done.
2. Fix open issues 2 to 4 (doc links, missing PNG, LLD.md status line).
3. Start Phase 2 (see the previous entry's next steps).
