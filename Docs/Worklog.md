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
| Phase | Phase 2 (durable chat loop: LangGraph + Neon checkpointer) **complete** and verified against real Neon and the real model; committed on `dev` as "Phase 2: durable chat loop on LangGraph and Neon" and pushed (see `git log`). Phase 1 is `21a074d`. |
| Branches | Work happens on `dev`; `main` deploys to Streamlit Cloud on push. `dev` = `origin/dev` = the Phase 2 commit (pushed 2026-10-07); `main` = `origin/main` = `bf58edf` |
| Last commit | `21a074d` "Phase 1: streaming chat page" on `dev` (2026-10-07); before that `bf58edf` Added HLD, LLD and architecture docs (`Docs/Architecture.md`, `HLD.md`, `LLD.md`, `Worklog.md`); before that `cd39644` Phase 0: project skeleton (2026-10-06) |
| Uncommitted | Nothing |
| Python | 3.12.15 in `.venv` (managed by uv); `requires-python >= 3.12` |
| Dev packages | pytest 9.1.1 (`[dependency-groups] dev`) |
| Key packages | langgraph 1.2.14, langgraph-checkpoint 4.2.0, langgraph-checkpoint-postgres 3.1.2, langchain-core 1.6.6, langchain-openai 1.6.7, streamlit 1.65.0, psycopg 3.3.6, psycopg-pool 3.3.3 |
| Tests | 23 pass + 1 skipped with `uv run pytest` (5.3 s, offline). The skipped one is `tests/test_integration.py`; it passes with `RUN_INTEGRATION=1` (29 s, real Neon + model) |
| Database | Neon, pooled endpoint (`-pooler` host, `sslmode` and `channel_binding` set). LangGraph checkpoint tables created by `PostgresSaver.setup()` on 2026-10-07. Which Neon branch the local `DATABASE_URL` points at (`dev` or `main`) was not checked |
| Secrets present locally | `HF_TOKEN`, `LLM_MODEL`, `LLM_BASE_URL`, `SERPAPI_KEY`, `OPENTRIPMAP_KEY`, `GEOAPIFY_KEY`, `DATABASE_URL` in `.streamlit/secrets.toml` (gitignored, checked) |

### Phase map

The design docs name phases but don't list them all. This table is what can be read from them; rows marked "not defined" need filling in when the plan is decided.

| Phase | Scope (from the docs) | Status |
| --- | --- | --- |
| 0 | Project skeleton: uv project, Streamlit hello page | Done, committed `cd39644` |
| 1 | `planner/llm.py` on the HF router with the LLD limits; `app.py` streaming chat sending the last 20 messages; error message and retype on failure; secrets `HF_TOKEN`, `LLM_BASE_URL`, `LLM_MODEL` | Done and committed 2026-10-07 |
| 2 | LangGraph engine (`graph/state.py`, `graph/build.py`, `nodes/chat.py`, `nodes/orchestrator.py`), `planner/db.py` checkpointer on Neon, trip id in URL, Retry button, AppTest | Done, committed and pushed on `dev` 2026-10-07. Walkthrough: [Phase2-Guide.md](Phase2-Guide.md) |
| 3 | Profiler and constraints agents, `planner/models.py` (`Preferences`, `TripInputs`); named Phase 3 by the user. **Written by the user**, guided by Claude | In progress (planned 2026-10-07) |
| 4 | Scoring weights tuned by hand (`scoring.py`) | Not started |
| 5 | Not defined in the docs | — |
| 6 | Live tools: SerpApi flights and hotels, OpenTripMap and Geoapify places | Not started |

### Open issues

| # | Issue | Status |
| --- | --- | --- |
| 1 | `pytest` is not a project dependency, so a bare `pytest` runs the global Python 3.11 install and the AppTest times out | Fixed 2026-10-07 |
| 2 | Doc cross-links use lowercase names (`hld.md`, `lld.md`, `architecture.md`) but the files are `HLD.md`, `LLD.md`, `Architecture.md`; links break on GitHub | Open |
| 3 | `architecture.png` is linked from Architecture.md and HLD.md but does not exist | Fixed 2026-10-07: the user added `Docs/architecture.png` (name matches both links) |
| 4 | LLD.md says Phases 0 to 2 match it and marks Phase 2 files as existing; only Phase 1 code exists | Mostly resolved by Phase 2 (all files marked "(Phase 2)" now exist). Remaining gaps: the layout roots at `travel-planner/` and lists a `ui/` package that doesn't exist yet (rendering is still in `app.py`); there is no `ui/debug.py` sidebar inspector |
| 5 | `planner/llm.py` lacks `timeout=60`, `max_retries=2`, `stream_usage=True` from the LLD limits table | Fixed 2026-10-07; writing the token counts to `usage` waits for the Phase 2 database |
| 10 | Gemini free tier allows only 20 requests/day per project per model (`gemini-3.5-flash`); about 10 user turns/day at 2 calls per turn. Too little for a public demo (2026-10-08) | Open, decision needed |
| 9 | Gemini API key printed into the chat by a careless `grep` (2026-10-08) | Open, the user rotates the key in Google AI Studio |
| 8 | Norton 360 quarantined `llama-server.exe` and `scripts/start_llm.ps1` (2026-10-08). The local dev model can't run until the user restores and excludes the exe; the launcher is to be rewritten as `start_llm.cmd` without reading secrets | No longer applies: the local model was dropped and its files deleted 2026-10-08 |
| 7 | Hugging Face Inference Providers credits are used up: every model call returns `402 You have no remaining credits` (first seen 2026-10-08). Blocks the live app, the integration test and live checks | Resolved 2026-10-08 by switching to Gemini (`gemini-3.5-flash`); HF lines removed from dev secrets |
| 6 | `uv` cannot reach PyPI without `--system-certs` (TLS `UnknownIssuer`), and `git push` fails with "unable to get local issuer certificate" unless run as `git -c http.sslBackend=schannel push`. Permanent git fix: `git config --global http.sslBackend schannel` | Open (environment) |

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
- Committed on 2026-10-07 at the user's request, on the `dev` branch (commit `21a074d`, "Phase 1: streaming chat page"). `main` and `origin/main` stay at `bf58edf`, so the deployed app is unchanged until `dev` is merged and pushed. (A first version of this note wrongly said `main`.) This worklog was updated in the same commit, so its own hash can't appear here; run `git log --oneline` to see it.

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

---

## 2026-10-07: Branch fix recorded, dev pushed

**Goal**
Correct the worklog's branch record, then commit and push `dev`.

**Changes**
- `Docs/Worklog.md`: the Phase 1 entry now says the commit is on `dev`, not `main`, and a Branches row was added to the status table. Committed on `dev` as `94b3e22` "Worklog: record that Phase 1 was committed on dev".
- After the push, this file was updated again: this entry, the Branches row (now pushed) and open issue 6 (git TLS). These edits are **not committed** yet and go in with the next commit on `dev`.

**Decisions**
- Pushed `dev` only. `main` was not merged or pushed, so the deployed app is unchanged.
- To get past the certificate error, used `-c http.sslBackend=schannel` for this one push, so git checks certificates against the Windows store. Did not turn off SSL verification, and did not change global git config.

**Verification**
- `git push origin dev` → `fatal: unable to access 'https://github.com/Drakeshaw10/travel-planner/': SSL certificate problem: unable to get local issuer certificate`.
- `git -c http.sslBackend=schannel push origin dev` → `bf58edf..94b3e22  dev -> dev`. `git status -sb` → `## dev...origin/dev`, in sync.
- Branches afterwards: `dev` = `origin/dev` = `94b3e22`; `main` = `origin/main` = `bf58edf`.

**Issues found**
- git has the same TLS certificate problem as uv (open issue 6, updated). Status: open, environment only.

**Next steps**
1. Optionally run `git config --global http.sslBackend schannel` so plain `git push` works.
2. Fix open issues 2 to 4 (doc links, missing PNG, LLD.md status line), or start Phase 2.

---

## 2026-10-07: Phase 2, durable chat loop on LangGraph and Neon

**Goal**
Replace Phase 1's in-memory chat with the LangGraph engine from LLD.md, with state checkpointed to Neon after every step. Wanted: a trip id in the URL that reopens the conversation, a Retry button that resumes a failed run from its checkpoint, and tests at every layer. The user asked for code they can learn from, so every file explains *why* it is written that way, and there is a walkthrough doc.

**Changes**
- `planner/graph/__init__.py`, `planner/graph/nodes/__init__.py`: new package markers, each with a one-line docstring.
- `planner/graph/state.py` (new): `TravelState` exactly as in LLD.md. `messages` uses the `add_messages` reducer; every other key is `NotRequired`, and the keys for later phases are declared now. Type alias `Phase`. The docstring explains why state is plain JSON and not Pydantic objects.
- `planner/graph/nodes/orchestrator.py` (new): `route(state)` as in LLD.md: `discovery` → `profiler`, `constraints` → `constraints`, anything else → `chat`, and no phase counts as `discovery`. Uses `match`. The other routers from LLD.md (`after_constraints`, `after_feasibility`, `after_budget`) are not added until their nodes exist.
- `planner/graph/nodes/chat.py` (new):
  - `GREETING` and `SYSTEM_PROMPT` moved here from `app.py`, text unchanged.
  - `greet`: returns the greeting and `phase="discovery"`; no LLM call.
  - `wait_for_user`: `interrupt("waiting_for_user")`; checks that the resume value is a non-empty `str` (raises `ValueError` otherwise); strips it; appends a `HumanMessage`; increments `user_turns`. The docstring explains how `interrupt` re-runs the node.
  - `make_chat(llm)`: a factory returning the `chat` node, which calls `llm.invoke([SystemMessage, *messages[-MAX_HISTORY:]])` and returns the reply.
- `planner/graph/build.py` (new):
  - `STREAMING_NODES = {"chat", "writer"}`.
  - `ROUTE_MAP` maps `route()`'s `profiler` and `constraints` answers to `chat` until those nodes exist.
  - `build_graph(llm, checkpointer)`: nodes `greet`, `wait_for_user`, `chat`; edges START → greet → wait_for_user, conditional `route` with `ROUTE_MAP`, chat → wait_for_user; `compile(checkpointer=...)`.
- `planner/db.py` (new):
  - `get_pool()` (`@st.cache_resource`): `ConnectionPool(DATABASE_URL, min_size=1, max_size=5, kwargs={autocommit: True, row_factory: dict_row, prepare_threshold: 0}, check=ConnectionPool.check_connection, max_lifetime=1800, open=True)`.
  - `get_checkpointer()` (`@st.cache_resource`): `PostgresSaver(pool)` plus `setup()`.
  - Comments tie each setting to the problem it solves; `prepare_threshold=0` is there because the URL is Neon's PgBouncer pooled endpoint.
- `app.py` (rewritten):
  - History is no longer kept in `st.session_state`.
  - `get_graph()` (`@st.cache_resource`) builds the graph from `get_llm()` and `get_checkpointer()`.
  - `current_trip_id()` reads `?trip=`, accepts only a valid UUID, and otherwise makes a new `uuid4` and writes it to the URL. `config = {"configurable": {"thread_id": trip_id}}`.
  - A new trip runs `graph.invoke({"messages": []})` to reach the first interrupt. History is drawn from `graph.get_state(config).values["messages"]`.
  - If `snapshot.interrupts` is set: show the chat input; on submit, `run_turn(Command(resume=prompt))`.
  - If `snapshot.next` is set with no interrupt (a failed run): show the error and a Retry button, which runs `run_turn(None)` and then reruns.
  - `stream_reply()` passes on only `AIMessageChunk` string tokens from `STREAMING_NODES`.
  - On failure, `run_turn()` logs with `logger.exception`, stores a friendly message in `st.session_state.last_error`, and reruns.
  - If the database can't be reached on load: friendly `st.error` and `st.stop()`; the raw exception is logged, not shown.
  - Sidebar: "New trip" writes a new UUID to the URL and reruns; a caption says to bookmark the page.
- `tests/fakes.py` (new): `FlakyModel` (fails its first `fail_times` calls in both `_call` and `_stream`, then answers) and `RecordingModel` (moved from `test_app.py`, now also records `_call`).
- `tests/test_orchestrator.py` (new): 6 parametrized `route` cases.
- `tests/test_graph.py` (new), 9 tests using `build_graph` + `InMemorySaver`:
  - new trip greets and waits;
  - resuming adds the stripped user message, the reply and `user_turns=1`;
  - an empty resume raises;
  - message streaming comes only from `chat` (and `wait_for_user`, which the UI filters out);
  - a failed node leaves `next=("chat",)` with no interrupt and the user message kept, and `invoke(None)` recovers;
  - state survives a new graph instance on the same saver;
  - threads are isolated;
  - the model gets the system message plus 20 messages;
  - `ROUTE_MAP` only points at existing nodes.
- `tests/test_app.py` (rewritten), 8 AppTests:
  - An autouse fixture clears `st.cache_resource` and swaps `get_checkpointer` for an `InMemorySaver`.
  - Tests: new trip gets a UUID in the URL and the greeting; chat round trip; reopening the link in a new session restores history; an invalid trip id is replaced; a model error shows Retry, hides the chat input and recovers on click; New trip switches the id and resets the chat; database down shows the friendly message without internals; LLM client settings.
- `tests/test_integration.py` (new): skipped unless `RUN_INTEGRATION=1`. Uses the real `get_checkpointer()` and `get_llm()`: starts a trip, sends one message, reads it back through a fresh graph, then `delete_thread()` in a `finally` block and checks the trip is gone.
- `Docs/Phase2-Guide.md` (new): learning walkthrough with a sequence diagram of one message, a "why" section per file, a table of pool settings, the testing strategy, commands, and what is left for later.
- `Docs/architecture.png`: added by the user (not by Claude); now part of this change set.
- No dependency changes. `requirements.txt` already had everything Phase 2 needs.

**Decisions**
- **`ROUTE_MAP` instead of a cut-down `route()`:** `route()` matches LLD.md now, and later phases change one map entry per agent. A test stops the map from pointing at a missing node.
- **Model injected via `make_chat(llm)`:** the graph package never reads secrets, which keeps LLD.md's rule that only `llm.py`, `db.py` and `cache.py` touch them.
- **`get_graph()` lives in `app.py`, not `build.py`:** caching is a Streamlit concern, and `build.py` stays free of Streamlit, so tests can import it directly.
- **Retry is driven by checkpoint state, not session state:** `snapshot.next` without `snapshot.interrupts` means a failed run. Retry therefore works after a refresh or from another device, not just in the tab that saw the error.
- **Friendly errors, full logs:** Phase 1 showed raw exception text to the user; Phase 2 logs it and shows a short message.
- **No `ui/` package yet:** LLD.md's `ui/chat.py` split was postponed while `app.py` is about 150 lines; the guide says when to split.
- **Tests kept offline by default:** the integration test is opt-in so `uv run pytest` needs no secrets, network or tokens.
- **Phase numbering:** comments say "later phase", not "Phase 3", because the docs don't define Phase 3 (an earlier draft said "Phase 3" and was corrected).

**Verification**
- Before writing code, checked the installed APIs: `StateSnapshot` fields include `interrupts`; `PostgresSaver(conn, pipe=None, serde=None)`; `ConnectionPool` accepts `check`, `max_lifetime`, `open`; `add_conditional_edges(source, path, path_map)`.
- Checked the shape of `DATABASE_URL` without printing it: scheme `postgresql`, Neon host with `-pooler`, query keys `channel_binding` and `sslmode`, database name set.
- First `uv run pytest -q` → 3 failed, 20 passed. Cause: in AppTest, `at.query_params["trip"]` is a plain `str` (checked: `<class 'dict'>`, value `'d52426f6-…'`), so the tests' `[0]` took one character. Fixed the tests; the app was fine.
- `uv run pytest -q` → **23 passed, 1 skipped in 5.3 s**.
- `RUN_INTEGRATION=1 uv run pytest tests/test_integration.py -v` → **1 passed in 29.4 s** against real Neon and the HF model. This was also the first `setup()` run, which created LangGraph's checkpoint tables on the Neon database in `DATABASE_URL`.
- Whole app against real services (`AppTest` on `app.py` with nothing patched):
  - first load 16.3 s (imports, pool open, `setup()`, Neon waking), greeting shown, no exception;
  - one turn ("Birdsong, and I hate crowds") 6.8 s, no errors, reply "Got it! Do you prefer a peaceful hike in nature or a relaxing stay at a quiet lodge?";
  - reopening the same trip id in a new session showed 3 messages;
  - the trip was then deleted with `delete_thread()`.
- Not checked: clicking through in a real browser.
- A first attempt to write this worklog entry failed on shell quoting before changing anything (checked with `git diff --stat`); it was redone from a script file.

**Issues found**
- First-load latency: 16 s on a cold start. Most of it is one-off per process (imports, pool, `setup()`), plus Neon's wake-up. Later page loads in the same process reuse the cached pool and graph. Status: note; recheck on Streamlit Cloud.
- It wasn't checked which Neon branch (`dev` or `main`) the local `DATABASE_URL` uses. HLD.md says to use `dev` locally. Status: open, for the user to confirm in the Neon console.
- Token counts are returned but not yet stored in `usage`. Status: deferred to the phase that adds `cache.py` and the tables from LLD.md.
- Open issue 3 fixed (PNG added); open issue 4 mostly resolved (see the table).

**Next steps**
1. Read `Docs/Phase2-Guide.md` and try the app: `uv run streamlit run app.py`, send a message, copy the URL into a new tab, and check the chat comes back.
2. Confirm the local `DATABASE_URL` points at the Neon `dev` branch.
3. ~~Commit Phase 2 on `dev` and push~~ Done. The commit includes this worklog, so its own hash isn't here; see `git log`. The earlier uncommitted worklog edits (the push entry) went into the same commit.
4. Fix open issue 2 (lowercase doc links).
5. Next phase: `planner/models.py` (`Preferences`, `TripInputs`), then the `profiler` and `constraints` nodes, switching their `ROUTE_MAP` entries and adding `after_constraints`.

---

## 2026-10-07: Phase 3 planned; the user now writes the code

**Goal**
Plan the next phase, which adds the `profiler` and `constraints` agents, and switch to the working style the user asked for.

**Working style from now on**
The user writes all implementation code. Claude splits the work into steps, explains the concepts and reasons, reviews the user's code, runs tests, and keeps this worklog. Phases 0 to 2 were written by Claude; from Phase 3 on, each entry says who wrote what.

**Phase 3 scope** (from LLD.md: "Graph nodes", "Routing rules", "Discovery scoring", "Config, errors, limits")
"Phase 3" is the user's name for this phase; the docs don't number it.

| Step | What the user writes | Done when |
| --- | --- | --- |
| 1 | `planner/models.py`: `Preferences` and `TripInputs`, the fixed tag vocabulary, and a merge rule for new answers | Models validate good input, reject bad input, and merging keeps old values |
| 2 | A spike script: does `with_structured_output(Preferences)` work with GPT-OSS-120B on the HF router, and with which `method`? | A recorded answer in this worklog |
| 3 | `planner/graph/nodes/profiler.py`: `make_profiler(llm)` | Preferences merged; `phase="constraints"` once complete or after 6 turns; a parse failure is retried once, then old values are kept |
| 4 | `planner/graph/nodes/constraints.py`: `make_constraints(llm)` | Trip details merged; `phase="selection"` once `missing()` is empty; relative dates work (today's date goes in the prompt) |
| 5 | `orchestrator.py`: `after_constraints`; `build.py`: new nodes, edges and `ROUTE_MAP` entries | Routing tests pass; the graph runs end to end with fakes |
| 6 | `chat` node uses `phase` and `trip.missing()` to ask the right next question | Asks about preferences in discovery and the missing trip details in constraints |
| 7 | Tests for steps 1 to 6, the integration test, and a manual browser check | `uv run pytest` passes; one real conversation reaches `phase="selection"` |

`scorer` doesn't exist in this phase, so `after_constraints` returning `"scorer"` needs a temporary mapping, in the same way `ROUTE_MAP` handles agents not built yet.

**Changes**
- `Docs/Worklog.md`: this entry. No code changes.

**Verification**
None (planning only).

**Next steps**
The user starts Step 1, `planner/models.py`.

---

## 2026-10-07: Phase 3 Step 1, `planner/models.py` (written by Claude at the user's request)

**Goal**
Add the `Preferences` and `TripInputs` models that the profiler and constraints nodes will fill from chat.

**Who wrote it**
Claude guided first: the plan, then a beginner walkthrough with a toy `Pizza` model. The user had created an empty `planner/models.py`, said "how do I start I have no idea", and then "just write the code". So Claude wrote `planner/models.py` and `tests/test_models.py`, with the reasons explained in comments. Lesson for later steps: start the user from a partial file or an example, not a blank file plus several design questions.

**Changes**
- `planner/models.py` (new):
  - The tag vocabulary is defined once per kind as a `Literal` type: `Setting` (beach, hills, forest, desert, backwaters, heritage, city), `Mood` (calm, adventurous, romantic, social, spiritual), `Interest` (food, trekking, wildlife, temples, history, nightlife, water sports, photography, wellness), `Avoid` (crowds, long drives, heat, cold, rain), `Pace`, `Mode`. Tuples `SETTINGS`, `MOODS`, `INTERESTS`, `AVOIDS`, `MODES` are derived from them with `typing.get_args()`.
  - Base class `Extracted(BaseModel)`:
    - `VOCAB: ClassVar[dict]` maps each tag-list field to its vocabulary.
    - A `field_validator("*", mode="before")` cleans tag lists: lower-case, trim, de-duplicate, turn a single string into a list and `None` into `[]`, and **drop** unknown tags rather than reject them.
    - `merged(new)` returns a copy where every value `new` actually provides (not `None`, not `[]`) replaces the old one; lists are replaced, not added to.
  - `Preferences(Extracted)`: `settings`, `moods`, `interests`, `avoid`, `pace`; `is_complete()` as in LLD.md (`avoid` optional).
  - `TripInputs(Extracted)`: fields and limits as in LLD.md, `missing()` as in LLD.md, plus a `travellers` property.
- `tests/test_models.py` (new), 26 tests:
  - completeness;
  - unknown tags dropped; tags normalised and de-duplicated; a single string and `None` handled;
  - an invalid `pace` rejected;
  - `missing()` order;
  - 7 limit violations;
  - an unknown mode dropped;
  - `travellers`;
  - the JSON round trip keeps `date`;
  - merge: keeps old values, replaces given values, replaces lists, ignores empty lists, keeps an explicit 0, leaves the original unchanged.

**Decisions** (and where they differ from LLD.md)
- **Unknown tags are dropped, not rejected:** with a strict `Literal`, one invented tag would fail the whole LLM answer and lose its good values. The JSON schema still lists the allowed values as `enum`, so the model is guided toward them.
- **`children` is `int | None = None`, not `int = 0` as in LLD.md:** this keeps "not said" separate from "no children". Otherwise `merged()` couldn't keep an explicit 0. `travellers` treats `None` as 0. `missing()` still doesn't include `children`. **This differs from LLD.md.**
- **Lists are replaced on merge, not combined:** this lets a user take something back. In exchange, the profiler and constraints prompts must show the LLM the current values and ask for full updated lists (to remember in Steps 3 and 4).
- **No past-date validator on the model:** "today" makes it hard to test, so the constraints node will check it.
- **Tag spelling follows LLD.md's examples, including "long drives" with a space.** `destinations.csv` must use exactly these words.
- `Candidate` and `PricedItem` from LLD.md are not added yet; they belong to the scorer and tools phases.

**Verification**
- `uv run pytest -q` → **49 passed, 1 skipped in 6.43 s** (26 new, 23 existing).
- `Preferences.model_json_schema()`: `settings.items.enum` lists the 7 settings; `pace` is `anyOf[enum, null]`. `VOCAB` is not in the schema. `TripInputs` schema fields: origin_city, start_date, nights, adults, children, budget_inr, modes.
- A first draft used a private `_vocab` attribute, which Pydantic wraps as a private attribute (it needed `.default` to read). It was changed to `VOCAB: ClassVar` before any test ran.

**Issues found**
- LLD.md's `children: int = 0` now differs from the code. Status: open; update LLD.md along with the other doc fixes (open issues 2 and 4).

**Next steps**
- Step 2: check that `get_llm().with_structured_output(Preferences)` works with GPT-OSS-120B on the HF router, and which `method` to use (`json_schema` or `function_calling`).
- Ask the user whether they want to write Step 2 themselves (from a partial file) or have Claude write it.

---

## 2026-10-07: Phase 3 Step 2, structured output spike (written by Claude at the user's request)

**Goal**
Before building the profiler and constraints nodes, find out whether GPT-OSS-120B on the HF router can fill `Preferences` and `TripInputs` through LangChain's `with_structured_output`, and which `method` to use.

**Who wrote it**
Claude, after the user said "write step 2 as well".

**Changes**
- `scripts/spike_structured_output.py` (new). It reads `.streamlit/secrets.toml` directly with `tomllib`, because the script runs outside Streamlit, and uses `temperature=0`, `timeout=60`, `max_retries=1`. It runs 3 cases (2 `Preferences`, 1 `TripInputs`) with each method: `json_schema`, `function_calling`, `json_mode`. It uses `include_raw=True` so failures are reported instead of raised, checks each result against what the answer should contain, and prints the result, the timing and a summary. The system prompts follow the plan for the real nodes: the fixed vocabulary from `planner.models`, today's date for `TripInputs`, and "leave it null if not said".
- Run with `uv run python -m scripts.spike_structured_output`. The first attempt, `uv run python scripts/spike_structured_output.py`, failed with `ModuleNotFoundError: No module named 'planner'`: running a file directly puts `scripts/` on `sys.path`, not the project root. The docstring now explains this.

**Verification** (one live run, 2026-10-07, 9 model calls)

| Method | Preferences: sea/relax/food/slow/no crowds | Preferences: adventurous/trek/wildlife/packed | TripInputs: Pune, 2+1, 2026-11-20, 4 nights, 60k, train/bus | Correct |
| --- | --- | --- | --- | --- |
| `json_schema` | correct, 0.9 s | correct, 0.5 s | correct, 0.4 s (all 7 fields) | 3/3 |
| `function_calling` | correct, 0.5 s | correct, 0.6 s | correct, 0.5 s (all 7 fields) | 3/3 |
| `json_mode` | correct, 0.7 s | correct, but added unrequested `settings: hills, forest`, 0.6 s | wrong: only `nights`, `adults`, `budget_inr`; lost origin, date, children, modes, 0.5 s | 2/3 |

**Decisions**
- **Use `method="json_schema"`** (LangChain's default for `ChatOpenAI`) in the profiler and constraints nodes. It was correct and fast in every case, and it sends the schema to the API, including the tag `enum`s.
- **`function_calling` is the fallback** if the router or model ever stops accepting `json_schema`; it was equally good here.
- **Don't use `json_mode`:** the schema only appears in the prompt, and it dropped fields and invented tags.
- The script is kept in `scripts/` as a reusable check. It can be rerun after a model or router change.

**Issues found**
- Small sample: 3 cases, one run, temperature 0. The real nodes will run at the client's `temperature=0.7` unless they set their own, and messy multi-turn chats are harder than these one-liners. Status: note; the tests in Steps 3 and 4 and the integration run will show more.
- LLD.md's error table already plans for parse failures ("retry once with the parse error added, then keep old values"). Steps 3 and 4 still need that, even though nothing failed here.

**Next steps**
Step 3: `planner/graph/nodes/profiler.py` with `make_profiler(llm)`. It uses `llm.with_structured_output(Preferences, method="json_schema", include_raw=True)`, a prompt showing the current preferences and the vocabulary, `merged()`, the 6-turn cap, and one retry on a parse error.

---

## 2026-10-08: Phase 3 Step 3, profiler node (written by Claude at the user's request)

**Goal**
Add the profiler node: during discovery, turn the chat into structured `Preferences`, merge them into state, and decide when discovery is over.

**Who wrote it**
Claude, after the user said "Write step 3 now".

**Changes**
- `planner/graph/nodes/profiler.py` (new):
  - Constants `RECENT_MESSAGES = 10` and `MAX_DISCOVERY_TURNS = 6`, both from LLD.md.
  - `SYSTEM_PROMPT` lists the fixed vocabulary, shows the known preferences as JSON, and asks for the *full* updated preferences: keep known tags unless the user changed their mind, add indirect hints ("waves" → beach), and leave unknowns empty.
  - `build_prompt(current)`.
  - `extract(extractor, messages)`: one call; on a parse error, logs a warning and retries once with a `HumanMessage` naming the error; on a second failure, logs and returns `None`. API errors are not caught, so the node fails and the Phase 2 Retry button handles it.
  - `make_profiler(llm)` builds `llm.with_structured_output(Preferences, method="json_schema", include_raw=True)` once. The node validates the current preferences from state, sends the system prompt plus the last 10 messages, merges with `merged()` (or keeps the current values if extraction returned `None`), stores `model_dump(mode="json")`, and sets `phase="constraints"` when `is_complete()` is true or `user_turns >= 6`.
  - The node is **not wired into the graph yet**; that is Step 5.
- `tests/fakes.py`: added `StructuredFake`, a stand-in model whose `with_structured_output()` returns a `RunnableLambda` giving the same `{raw, parsed, parsing_error}` dict as LangChain's `include_raw=True`. Results are queued as model instances (parse succeeds) or strings (parse fails). It records `calls` and `options`.
- `tests/test_profiler.py` (new), 10 tests:
  - uses `json_schema` with `include_raw`;
  - a partial answer is saved and discovery continues;
  - merging with known preferences;
  - complete preferences → `constraints`;
  - the turn cap → `constraints`;
  - a parse error is retried once with the error text;
  - two parse errors keep the old preferences, with no third call;
  - the prompt contains the vocabulary and the current preferences;
  - only system plus 10 messages are sent;
  - an API error propagates (`pytest.raises`).

**Decisions**
- **The profiler doesn't speak to the user.** It only updates state; the `chat` node asks the next question (LLD.md graph: `profiler → chat`). Its LLM call isn't streamed to the UI because `profiler` isn't in `STREAMING_NODES`.
- **Current preferences go in the prompt**, as Step 1 required, because `merged()` replaces lists.
- **The extractor is built once per node**, not on every call.
- **Extraction temperature stays at the client's 0.7.** `with_structured_output` returns a chain, so it can't simply be given `temperature=0`. Step 2 showed `json_schema` works well; revisit if extraction proves unstable. Status: note.

**Verification**
- `uv run pytest -q` → **59 passed, 1 skipped in 16.4 s** (10 new). After changing the last test to `pytest.raises`: `tests/test_profiler.py` → 10 passed in 0.54 s.
- Live check (the real profiler with the real model, two scripted turns, including a change of mind) **could not run**: `openai.APIStatusError: Error code: 402 - {'error': 'You have no remaining credits. Purchase pre-paid credits to continue using Inference Providers. Alternatively, subscribe to PRO to get monthly included credits.'}`. Not retried.

**Issues found**
- **HF credits used up** (open issue 7). This also affects the deployed app on `main`: every chat reply will fail. Users would see "Something went wrong" and a Retry button that can't succeed until credits are added. Status: open, needs the user.
- Follow-up idea: a 402 (and 401) isn't something Retry can fix, so the UI could say "the planner is temporarily unavailable" instead of offering Retry. Status: open, not started.

**Next steps**
1. The user restores HF credits; then rerun the profiler live check and `RUN_INTEGRATION=1 uv run pytest tests/test_integration.py`.
2. Commit Steps 1 to 3 on `dev`.
3. Step 4: the constraints node.

---

## 2026-10-08: Local model option checked (DavidAU LFM2.5-2.6B GGUF)

**Goal**
The user asked whether `DavidAU/LFM2.5-2.6B-Qwen3.8-Turbo-Brilliance-Power-X12-NEO-MAX-GGUF` (file `LFM2.5-2.6B-Q3.8-TBrilliance-NEO-MAX-Q6_K.gguf`, downloaded with `huggingface-cli download ... --local-dir ./`) can replace the HF API (out of credits, open issue 7), and how that would differ.

**Findings**
- **The file is not on this machine.** There is no `.gguf` anywhere on `C:\`, which is the only drive (full recursive search, including hidden files). It's also not in `~/.cache/huggingface` or in the project. The download didn't complete or never ran.
- No local model runner is installed: no `ollama`, `llama-server` or `lms`. `huggingface-cli` and `hf` exist in the global Python 3.11.
- Hardware: Ryzen 7 5800H (8 cores / 16 threads), 15.9 GB RAM (2.5 GB free at the time), RTX 3050 Laptop with 4 GB VRAM, 33.2 GB free on C:.
- Model, from the HF API and model card:
  - base `LiquidAI/LFM2.5-2.6B`, GGUF architecture `lfm2`, licence Apache 2.0, context 131,072, Q6_K about 2 GB;
  - DavidAU's "Turbo-Brilliance" add-on (12 reasoning and 12 instruct modes) is a community modification;
  - the card says it is "a pure reasoning model that always thinks before it answers" and "is not recommended for agentic coding and knowledge-heavy tasks";
  - recommended temperature 0.1 (Liquid AI), ChatML template.

**Assessment given to the user**
- Works for **local development only**, through llama.cpp `llama-server` (OpenAI-compatible). Only `secrets.toml` (`LLM_BASE_URL`, `LLM_MODEL`, a dummy `HF_TOKEN`) would change, because `planner/llm.py` already uses `ChatOpenAI` with `base_url`.
- **Can't serve the deployed app:** Streamlit Community Cloud has no GPU and too little memory, and self-hosting would break the $0 hosting rule.
- Differences from the API:
  - much lower quality (2.6B vs 120B), most noticeable in the chat and writer prose;
  - `<think>` text leaks into replies unless llama-server parses reasoning;
  - with `json_schema` the output is forced to JSON from the first token, so the model can't reason first;
  - it is an unofficial variant (the official LiquidAI GGUF is suggested instead);
  - the Step 2 spike needs rerunning against it.
- Also suggested: the same `gpt-oss-120b` from a provider with a free tier (Groq was named as an example). Only secrets would change, the Step 2 results still hold, and it works when deployed. Its free limits were **not checked**.

**Changes**
- `.gitignore`: added `*.gguf` and `models/` under a comment, so a multi-GB model downloaded into the project can't be committed. Checked with `git check-ignore -v test.gguf` → `.gitignore:6:*.gguf`.

**Next steps**
The user chooses between a local model (Claude guides the llama.cpp install and download, then reruns the spike) and a free-tier hosted API (pick a provider, update secrets). Steps 1 to 3 are still uncommitted.

---

## 2026-10-08: Decision: local model for dev, free-tier hosted model for production

**Decision (by the user)**
- **Development:** a local model served by llama.cpp's `llama-server` on this laptop.
- **Production** (`main`, Streamlit Cloud): a free-tier hosted OpenAI-compatible API, set up when the app goes live. The provider is not chosen yet; `gpt-oss-120b` on Groq was suggested, but its limits are not checked.
- No code change is needed to switch: `planner/llm.py` reads `LLM_BASE_URL`, `LLM_MODEL` and `HF_TOKEN` from secrets. The local `.streamlit/secrets.toml` points at llama-server, and Streamlit Cloud's secrets point at the hosted API.

**Facts gathered for the setup** (2026-10-08)
- GPU: RTX 3050 Laptop, 4096 MiB, driver **546.30, CUDA 12.3**.
- llama.cpp latest release `b11491` (2026-10-08). Its Windows x64 builds: `cpu`, `cuda-12.4`, `cuda-13.4`, `vulkan`, `sycl`, `openvino`, `rocm`. **The CUDA builds need a driver for CUDA ≥ 12.4, and this one supports 12.3, so the Vulkan build (`llama-b11491-bin-win-vulkan-x64.zip`) was chosen.** Updating the NVIDIA driver would make the CUDA build possible later.
- `winget search llama.cpp` found no package (the msstore source also needs its agreements accepted).
- Model: Liquid AI's official `LiquidAI/LFM2.5-2.6B-GGUF` instead of DavidAU's variant. Files include `LFM2.5-2.6B-Q6_K.gguf`, `Q5_K_M`, `Q4_K_M`, `Q8_0`. Architecture `lfm2`, context 131,072. Licence `lfm1.0` (Liquid's LFM Open License, **not Apache 2.0** like the DavidAU repo states); to be read before any commercial use.
- A possible reason the earlier `huggingface-cli download` left no file: this machine's TLS interception (open issue 6) also affects Python downloads. Not confirmed; the guide uses a browser download to avoid it.

**Changes**
None yet. A step-by-step setup guide was given to the user: binaries outside the repo, the model in the ignored `models/` folder, a `scripts/start_llm.ps1` launcher, dev secrets, a health check, and rerunning the Step 2 spike.

**Next steps**
The user follows the setup guide; then the Step 2 spike is rerun against the local model and the results are compared with GPT-OSS.

---

## 2026-10-08: Local model setup run by Claude; Norton quarantined the server and launcher

**Goal**
Do the local-model setup from the previous entry, at the user's request ("you run the download and setup commands").

**Changes**
- **llama.cpp** `b11491` Vulkan build, downloaded with `curl.exe`, which uses the Windows certificate store and so avoids open issue 6.
  - Checked first: SHA-256 `ebcee6f1…5e3729` matches GitHub's published asset digest; uploader `github-actions[bot]`.
  - Unzipped to `C:\Users\Aarush\tools\llama.cpp` (outside the repo). `--version` → `0.6.0-dev (build 11491, commit 9b4ed0ca5)`; `--list-devices` → `Vulkan0: NVIDIA GeForce RTX 3050 Laptop GPU (3977 MiB, 3380 MiB free)`.
- **Model** `LiquidAI/LFM2.5-2.6B-GGUF` / `LFM2.5-2.6B-Q6_K.gguf`, downloaded with `curl.exe` to `models/` (gitignored). Size 2,221,615,104 bytes and SHA-256 `2E74B1A0…9C250D` both match the Hugging Face API's LFS metadata.
- **`scripts/start_llm.ps1`** created, with params for the llama dir, the model path and the port. It checked that the exe and the model exist, and ran `llama-server` with `--alias lfm2.5-2.6b --host 127.0.0.1 --n-gpu-layers 99 --ctx-size 8192 --jinja`.
  - First run failed: `couldn't bind HTTP server socket, hostname: 127.0.0.1, port: 8080`. Port 8080 belongs to **TNSLSNR** (Oracle DB listener, pid 7200), so the port was changed to **8081** (checked free).
  - llama-server warned `no API key is set and CORS allows all origins`, so `--api-key` was added. The script read the key from the `HF_TOKEN` line of `.streamlit/secrets.toml`.
  - Second run: the model loaded in 8.6 s, `n_slots = 4, n_ctx_slot = 8192`, `listening on http://127.0.0.1:8081`. The process then stopped, because it was tied to Claude's background PowerShell session.
- **`.streamlit/secrets.toml`** (gitignored; values never printed): the `HF_TOKEN`, `LLM_BASE_URL` and `LLM_MODEL` lines were commented out, not deleted. New values added: `HF_TOKEN = "local-<random 24-byte token>"` (also the server's API key), `LLM_BASE_URL = "http://127.0.0.1:8081/v1"`, `LLM_MODEL = "lfm2.5-2.6b"`. `git check-ignore` confirmed the file is still ignored.

**What went wrong**
- A third launch, `Start-Process ... -WindowStyle Hidden`, failed because `start_llm.ps1` no longer existed. Checks found **`llama-server.exe` gone** from the tools folder as well (the other 50 files remain). The model, secrets and spike script are intact.
- Windows Defender had no detections (event IDs 1116–1119 in the last 2 hours). Installed antivirus: **Norton 360** and Windows Defender. The user then reported a **Norton quarantine notification**.
- Likely causes (not yet confirmed from Norton's history):
  - `llama-server.exe`: a reputation-based false positive on a newly built, unsigned binary. Its hash had been checked against GitHub's.
  - `start_llm.ps1`: heuristics, because a PowerShell script started with `-ExecutionPolicy Bypass` that reads a secrets file and extracts a token looks like an info-stealer. **This was a design mistake in the launcher.**

**Decisions**
- Claude will not change Norton settings or restore quarantined items. The user checks Norton's quarantine list and decides; the suggestion is to restore `llama-server.exe` and exclude `C:\Users\Aarush\tools\llama.cpp`.
- `start_llm.ps1` will not be restored. Planned replacement: `scripts/start_llm.cmd`, a batch file (no execution-policy bypass) that doesn't read `secrets.toml`. It will use `--api-key-file` with a gitignored `.llm-api-key` holding the same value as the dev `HF_TOKEN`.

**Open issues**
- Open issue 8 (new): Norton quarantined `llama-server.exe` and `start_llm.ps1`; the local model can't run until the user restores and excludes the exe.

**Next steps**
1. The user reports the file and threat names from Norton's quarantine, then restores and excludes `llama-server.exe` if it's a reputation detection.
2. Claude writes `scripts/start_llm.cmd` and `.llm-api-key`, adds the key file to `.gitignore`, starts the server as a separate long-running process, and checks `/health`.
3. Rerun the Step 2 spike against the local model.

---

## 2026-10-08: Local model dropped; switching to the Gemini API free tier

**Decision (by the user)**
The local llama.cpp route is abandoned after the Norton quarantine ("chuck it"). Instead, the user will provide a **Gemini API key (free tier)** for development; it can serve production too.

**Facts checked** (2026-10-08, from the providers' docs)
- **Gemini OpenAI compatibility** (ai.google.dev/gemini-api/docs/openai):
  - base URL `https://generativelanguage.googleapis.com/v1beta/openai/`;
  - structured output, streaming and function calling are all listed as supported;
  - "Support for the OpenAI libraries is still in beta".
  - So `planner/llm.py` (`ChatOpenAI` + `base_url`) should work unchanged. Only secrets change.
- **Gemini models** listed on the pricing page: `gemini-3.8-flash` (newest), `3.7-flash`, `3.6-flash`, `3.5-flash`, `3.5-flash-lite`, `3.1-flash-lite`. A free tier exists for the Flash models.
- **Gemini free-tier privacy:** "Used to improve our products": **Free tier: Yes**, paid tier: No. Fine for a portfolio demo whose trips hold no personal data (HLD.md, Security), but it should be said in the app or README if real users ever use it.
- **Hugging Face credits** (huggingface.co/docs/inference-providers/pricing): one money balance per account, spent across all models and providers. Free users get **no** monthly credits; PRO gets $2.00/month; Team and Enterprise get $2.00 per seat. **Switching models does not give more quota.**

**State left behind by the local-model attempt**
- `.streamlit/secrets.toml` currently points at the local server (`127.0.0.1:8081`, `lfm2.5-2.6b`, a random local key); the HF lines are commented out. This must be replaced with Gemini values.
- `models/LFM2.5-2.6B-Q6_K.gguf` (2.2 GB, gitignored) and `C:\Users\Aarush\tools\llama.cpp` (50 files; `llama-server.exe` quarantined by Norton) remain on disk. Deleting them waits for the user's OK.
- Open issue 8 (Norton) no longer blocks anything. Open issue 7 (HF credits) is worked around by switching providers.

**Next steps**
1. The user adds the Gemini key to `.streamlit/secrets.toml` themselves (not pasted in chat).
2. Claude checks it without printing it, reruns the Step 2 spike against Gemini, then runs the integration test and the Step 3 profiler live check.
3. Optional cleanup of the local-model files.

---

## 2026-10-08: Gemini set up, `HF_TOKEN` renamed to `LLM_API_KEY`, local model deleted

**Goal**
At the user's request: start using the Gemini key the user added, rename the secret, delete the local-model files, and run the checks the HF credits error had blocked.

**Changes**
- `.streamlit/secrets.toml` (gitignored; values not recorded here):
  - Removed the local-model block (old lines 9–14). It left a duplicate `HF_TOKEN`, so the file failed with `TOMLDecodeError: Cannot overwrite a value (at line 12)`.
  - Renamed the user's `HF_TOKEN` line to `LLM_API_KEY`.
  - `LLM_MODEL` changed from `gemini-3.8-flash` to **`gemini-3.5-flash`** (see the results below). `LLM_BASE_URL` = `https://generativelanguage.googleapis.com/v1beta/openai/`.
  - The file parses; keys: DATABASE_URL, GEOAPIFY_KEY, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, OPENTRIPMAP_KEY, SERPAPI_KEY.
- `planner/llm.py`: `api_key=st.secrets["LLM_API_KEY"]`; the module docstring now says any OpenAI-compatible provider, chosen only by secrets.
- `tests/test_app.py`: the settings test uses `LLM_API_KEY` and also checks `llm.openai_api_key.get_secret_value() == "test-token"`.
- `scripts/spike_structured_output.py`:
  - reads `LLM_API_KEY`;
  - new command-line options `--model` (override `LLM_MODEL`), `--methods` (subset of methods) and `--pause` (seconds before each call, for free-tier per-minute limits);
  - `run(model_name, methods, pause)` prints the model in use. The argument is called `model_name` so it doesn't clash with the loop variable `model`.
- `Docs/LLD.md`: the secrets table row now reads `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`, with a note about the rename and Gemini.
- **Deleted** (all created by the local-model attempt; checked first): `models/` (`LFM2.5-2.6B-Q6_K.gguf`, 2.07 GB), `C:\Users\Aarush\tools` (contained only `llama.cpp`, 51 files, 0.09 GB), `%TEMP%\llama-dl-b11491` (the zip), and `%TEMP%\llama-server-dev*.log`. All confirmed gone. `.gitignore` keeps `*.gguf` and `models/` in case a model is ever added again.

**Incident: Gemini API key printed into the chat**
To find references to `HF_TOKEN`, Claude ran `grep -rn "HF_TOKEN" ...`, which also matched `.streamlit/secrets.toml` and printed whole lines, including **the new Gemini key** and the now-useless local key. The Gemini key must be treated as exposed. **The user was asked to make a new key in Google AI Studio, delete the old one, and update `secrets.toml`.** Rule from now on: searches exclude `.streamlit/`, and that file is only read with its values masked.

**Verification**
- `uv run pytest -q` → **59 passed, 1 skipped in 6.38 s**.
- First spike on `gemini-3.8-flash` (all 3 methods): json_schema 1/3 correct (the success took 13.6 s); the other calls returned `503 This model is currently experiencing high demand`, then `429 You exceeded your current quota`. The rate-limits doc publishes no numbers; it says "Rate limits are applied per project, not per API key", that RPD resets at midnight Pacific, and that actual limits are shown in AI Studio.
- One-request probe per model (no retries), after the 429s had cleared, so the limit was per minute:

| Model | Result | Time |
| --- | --- | --- |
| `gemini-3.8-flash` | OK | 49.1 s |
| `gemini-3.5-flash` | OK | 1.9 s |
| `gemini-3.5-flash-lite` | OK | 1.0 s |
| `gemini-3.1-flash-lite` | OK | 7.0 s |

- Spike with `--methods json_schema function_calling --pause 4`:

| Model | json_schema | function_calling | Per call |
| --- | --- | --- | --- |
| `gemini-3.5-flash` | 3/3, exact | 3/3, exact | 2.0–3.7 s |
| `gemini-3.5-flash-lite` | 3/3, but added unrequested mood `romantic` | 2/3 (dropped trekking and wildlife) | 1.0–1.4 s |

- `RUN_INTEGRATION=1 uv run pytest tests/test_integration.py` → **1 passed in 21.3 s** (real Neon + `gemini-3.5-flash`).
- **Profiler live check** (blocked since Step 3), `gemini-3.5-flash`, temperature 0.7:
  - Turn 1, "Birdsong… misty mornings and long walks in the forest" (4.5 s) → settings `forest, hills`, moods `calm`, interests `trekking`, pace `None`; still in discovery.
  - Turn 2, "Calm, slow days, good local food. Actually forget the forest, I'd rather be up in the hills" (3.5 s) → settings **`hills`** (forest removed), moods `calm`, interests `trekking, food`, pace `slow`, and `phase: constraints`. **The replace-on-merge change-of-mind design works with a real model.**

**Decisions**
- Dev model: **`gemini-3.5-flash` with `json_schema`**. It was the most accurate and fast enough. `gemini-3.8-flash` was too overloaded on the free tier.
- Production will use the same provider. **When `dev` is merged into `main`, Streamlit Cloud's secrets must be updated in the same deploy:** rename `HF_TOKEN` to `LLM_API_KEY` and set the Gemini URL and model. Otherwise the deployed app fails with a missing secret.

**Issues found**
- Gemini key exposed in the chat (above). Status: open, needs the user to rotate it.
- Free-tier rate limits: a fast burst of calls hits 429. The app makes 2 LLM calls per discovery turn (profiler + chat), so heavy use could hit the limit. A 429 currently shows "Something went wrong" + Retry, which works once the minute has passed. Status: note; consider a friendlier message for 429.
- Open issue 7 (HF credits) is resolved by the provider switch. Open issue 8 (Norton) no longer applies, since the local model was deleted.

**Next steps**
1. The user rotates the Gemini key.
2. Commit Phase 3 Steps 1 to 3 plus this switch on `dev`.
3. Step 4: the constraints node.

---

## 2026-10-08: Phase 3 Steps 1–3 committed; Step 4, constraints node (written by Claude at the user's request)

**Commit**
Before the push, a secret scan of the staged diff found 0 matches each for `AIza`, `AQ.Ab`, `hf_…`, `local-…` and `postgres://user:pass@`, and `secrets.toml` was not staged. Committed `0d68df0` "Phase 3 steps 1-3: models, structured output spike, profiler; switch to Gemini" on `dev` and pushed (`6e7c904..0d68df0`). `main` is unchanged at `bf58edf`.

**Goal**
The constraints node: during `phase == "constraints"`, extract `TripInputs` from chat, merge them, and move to `selection` when the trip is fully described.

**Changes**
- `planner/graph/nodes/extraction.py` (new): `extract(extractor, messages, label)`, moved out of `profiler.py` so both nodes share the "call, retry once with the parse error, then give up and return `None`" logic. `label` names the node in log messages. API errors still propagate.
- `planner/graph/nodes/profiler.py`: its own `extract()`, `logging` and `HumanMessage` import removed; it now calls `extract(extractor, messages, "profiler")`. Its 10 tests passed unchanged after the move.
- `planner/graph/nodes/constraints.py` (new):
  - `RECENT_MESSAGES = 10`.
  - `SYSTEM_PROMPT` includes today's date and weekday, and explains each field: a "3-day trip" is 2 nights; adults are 12+; `budget_inr` is the group total ("60k" = 60000, "1.5 lakh" = 150000, per-person × travellers); "anything is fine" means all modes. It shows the known trip as JSON and says "never guess".
  - **Date rule:** "If no year is given, pick the year that puts the date closest to today, even if that date has already passed: report what the user said, don't correct it."
  - `build_prompt(current, today)`.
  - `drop_past_date(found, today) -> (TripInputs, problems)` drops a `start_date < today` and returns a problem message such as "The start date 01 October 2026 has already passed (today is 08 October 2026)."
  - `make_constraints(llm, today=date.today)`: the clock is injected and called on every run (the process can stay up past midnight). The node uses `json_schema` + `include_raw`, merges, writes `trip` and **`trip_problems`** (rewritten every run), and sets `phase="selection"` only when `missing()` is empty **and there are no problems**.
  - **Not wired into the graph yet** (Step 5).
- `planner/graph/state.py`: new `trip_problems: NotRequired[list[str]]`, commented as **not in LLD.md**.
- `tests/test_constraints.py` (new), 16 tests with a fixed `TODAY = 2026-10-08`:
  - schema options;
  - a partial answer is saved;
  - merging;
  - complete → `selection`; children not required;
  - a past date is dropped, with the exact problem text;
  - a past date doesn't erase a good known date and **doesn't move on**;
  - today is a valid start date;
  - no problems when everything is fine;
  - problems clear on the next turn;
  - parse retry; two parse errors keep the trip;
  - the prompt has today and the known trip;
  - today is read on every run;
  - only recent messages are sent;
  - an API failure propagates.

**Verification**
- `uv run pytest -q` → **75 passed, 1 skipped in 5.5 s**.
- Live on `gemini-3.5-flash` (today 2026-10-08, Thursday), four turns:
  - "leaving from Bengaluru next Friday, 3 nights" → Bengaluru, **2026-10-16**, 3 nights (5.2 s);
  - "Two of us plus our 8 year old. Around 1.5 lakh total, train or flight" → adults 2, children 1, **150000**, modes train + flight, phase selection (3.8 s);
  - "make it 5 nights, and we can only do 20k per person" → 5 nights, **60000** (20k × 3) (7.8 s);
  - "start on 1st October instead?" → **2027-10-01** with the first prompt. ❌ Bug: the "next time that date comes round" rule moved the trip a year ahead without saying so.
- After the date-rule fix: "1st October" (with a known trip) → dropped, old 2026-10-16 kept; "5th January" → **2027-01-05**; "20th November" → **2026-11-20**.
- After adding `trip_problems`, one live call: `trip_problems: ['The start date 01 October 2026 has already passed (today is 08 October 2026).']`, but `phase: selection`. That led to the "no problems" condition, so the node now stays in `constraints` (covered by a test; not re-run live).

**Decisions**
- **Report the date the user said, then validate in code**, instead of letting the prompt "fix" past dates by moving them to next year.
- **Rejections are recorded in state (`trip_problems`)** so Step 6's chat node can explain them, rather than ignoring the request silently.
- **Open problems block the move to `selection`.**
- "next Friday" said on a Thursday was read as 9 days ahead (2026-10-16). Some people mean tomorrow. Status: note; the chat node could confirm dates in Step 6.

**Issues found**
- `origin_city` is free text. It will need matching against the `origins` table when the scorer and feasibility nodes arrive.

**Next steps**
- Step 5: `after_constraints`, `ROUTE_MAP` entries for `profiler` and `constraints`, the graph edges, and graph tests.
- Step 6: the chat node reads `phase`, `preferences`, `trip.missing()` and `trip_problems`.

---

## 2026-10-08: Step 4 committed; Phase 3 Step 5, profiler and constraints wired into the graph (written by Claude)

**Commit**
`011de6c` "Phase 3 step 4: constraints node and shared extraction helper", on `dev`, pushed.
- The pre-commit secret scan reported `AIza=1 AQ=1 pg=1`, and the command **did not stop the commit**.
- Checked straight after (lines printed with masking): the only match is this worklog's own sentence describing the earlier scan, which names the patterns as text. **No secret was committed.**
- Process fix: the scan now uses real key shapes (e.g. `AIza[0-9A-Za-z_-]{35}`) and must abort the commit on any match.

**Changes**
- `planner/graph/nodes/orchestrator.py`: `after_constraints(state)` returns `"scorer"` when `phase == "selection"`, otherwise `"chat"` (LLD.md).
- `planner/graph/build.py`:
  - `ROUTE_MAP` now points `profiler` and `constraints` at their real nodes.
  - New `AFTER_CONSTRAINTS_MAP = {"scorer": "chat", "chat": "chat"}`; `scorer` is mapped to `chat` until that node exists.
  - `build_graph(llm, checkpointer, *, today=date.today)` adds nodes `profiler` (`make_profiler(llm)`) and `constraints` (`make_constraints(llm, today=today)`), the edge `profiler → chat`, and the conditional edge `constraints → after_constraints`.
  - Docstrings updated (Gemini; why `today` is keyword-only).
- `tests/fakes.py`:
  - New `FakeChat(FakeListChatModel)`, which answers chat from `responses` and `with_structured_output(Schema)` from an `extractions` queue (a model instance = a good parse, a string = a parse error, an empty queue = `Schema()`). It asserts the queued type matches the schema the node asked for.
  - `FlakyModel` and `RecordingModel` now subclass it.
  - `StructuredFake` no longer re-imports `RunnableLambda` locally.
  - Needed because `build_graph` now calls `with_structured_output`, which plain fakes don't support.
- `tests/test_graph.py`, `tests/test_app.py`: `FakeListChatModel` replaced with `FakeChat`.
- `tests/test_orchestrator.py`: 3 `after_constraints` cases.
- `tests/test_graph.py`, 6 new flow tests using `stream_mode="updates"` to list the nodes that ran:
  - a discovery turn runs `wait_for_user → profiler → chat`;
  - complete preferences hand over to `constraints` on the next turn (`wait_for_user → constraints → chat`);
  - a complete trip → `selection`, the graph still pauses;
  - a rejected value keeps the trip in `constraints` with a problem message;
  - the 6-turn cap moves on with incomplete preferences;
  - messages in `selection` go straight to `chat`.
  - The map test now covers both maps.

**Verification**
- `uv run pytest -q` → **84 passed, 1 skipped in 9.7 s** (9 new). All 75 earlier tests passed unchanged after the wiring and fake changes.
- **Live, whole app** (AppTest on `app.py`, real Gemini `gemini-3.5-flash` and Neon):
  - Turn 1, "Birdsong for sure. Misty hills, calm and slow days, and great local food." (16.7 s): no error.
  - Turn 2, "We're 2 adults from Pune, leaving 20th November for 4 nights, 60k total, train only." (10.7 s): the **constraints node succeeded**, but the chat node failed with **`429 RESOURCE_EXHAUSTED … Quota exceeded for metric generate_content_free_tier_requests, limit: 20, model: gemini-3.5-flash`, quotaId `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, retry in 16h30m**.
  - The app showed "Something went wrong while I was replying." with Retry, and no exception.
  - State read back from Neon: `phase: selection`; preferences `hills / calm / food / slow`; trip `Pune, 2026-11-20, 4 nights, 2 adults, 60000, train`; `trip_problems: []`; `next: ('chat',)`, not waiting for the user. So Retry would resume at `chat`, as designed.
  - The trip was then deleted (`delete_thread`, checked).
- Harmless warning seen: a Pydantic `PydanticSerializationUnexpectedValue` for `parsed` in LangChain's `include_raw` output during `stream_mode="messages"`. Status: note.

**Issues found**
- **Gemini free tier: 20 requests per day, per project, per model** for `gemini-3.5-flash`. The quota resets at midnight Pacific. With 2 LLM calls per user turn (profiler or constraints, plus chat), that is about **10 user messages a day for the whole app**. Fine for slow dev work, **not enough for a public demo**. Today's quota was used up by the spikes, the probes, the integration test and the live checks. Status: open, decision needed (see options given to the user).
- A 429 with a daily-quota cause gets the same "Something went wrong" + Retry, but Retry can't succeed for hours. The UI should say the planner is out of quota until tomorrow. Status: open.

**Next steps**
1. The user picks a quota approach.
2. Commit Step 5.
3. Step 6: phase-aware chat node (it uses `phase`, `preferences`, `trip.missing()` and `trip_problems`).
