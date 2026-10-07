# Architecture

One Streamlit app talks to Neon Postgres and five outside services. The browser only talks to the app, and Neon is the one place state lives, so a sleeping or redeployed app loses nothing.

See [hld.md](hld.md) for the components and flows, and [lld.md](lld.md) for the detail behind each box.

## System view

Arrows point from caller to callee. The LangGraph engine is the core: it saves state to Neon after every step and hands each turn to the right agent.

```mermaid
flowchart LR
    browser["<b>Browser</b><br/>chat in the browser<br/>?trip=uuid link"]

    subgraph cloud["Streamlit Community Cloud"]
        direction TB
        ui["<b>Chat UI (app.py)</b><br/>streams replies, shows shortlist<br/>and the costed itinerary"]
        engine["<b>LangGraph engine</b><br/>routes each turn, pauses with<br/>interrupt(), resumes on reply"]
        agents["<b>Agents (graph nodes)</b><br/>profile, score, shortlist,<br/>plan, budget, write"]
        tools["<b>Tools layer + cache</b><br/>typed wrappers, 72 h cache,<br/>SerpApi quota counter"]
        files["<b>Reference files (planner/data/)</b><br/>train and bus fares, entry fees"]
        ui --> engine --> agents --> tools --> files
    end

    neon[("<b>Neon Postgres (free)</b><br/>checkpoints per trip<br/>destinations, origins<br/>api_cache, 72 h<br/>usage counters<br/>dev and main branches")]
    hf["<b>Hugging Face router</b><br/>GPT-OSS-120B<br/>OpenAI-compatible API"]
    apis["<b>Travel APIs</b><br/>SerpApi flights, hotels<br/>OpenTripMap, Geoapify<br/>Open-Meteo weather"]

    browser -- chat --> ui
    engine -- state --> neon
    agents -- places --> neon
    tools -- cache --> neon
    agents -- LLM --> hf
    tools -- HTTPS --> apis

    classDef core fill:#dbe8fb,stroke:#2f6fdb,stroke-width:2px;
    class engine core;
```

The same picture as an image, for places that don't render Mermaid: [architecture.png](architecture.png).

## Agent graph

Thirteen LangGraph nodes. `logistics` and `experience` run in parallel; `budget` sends the plan back to one of them, up to 3 rounds, before `writer` runs. Every `wait_for_user` and `pick` is an `interrupt()` that saves state to Neon and waits for the next message or click.

```mermaid
flowchart TD
    START([START]) --> greet
    greet --> wait[wait_for_user]
    wait -- "phase = discovery" --> profiler
    wait -- "phase = constraints" --> constraints
    wait -- "phase = done" --> chat
    profiler --> chat
    constraints -- "something missing" --> chat
    constraints -- "trip complete" --> scorer
    chat --> wait
    scorer --> feasibility
    feasibility -- "nothing fits budget" --> chat
    feasibility -- "candidates" --> shortlist
    shortlist --> pick
    pick -- "user picks a destination" --> logistics
    pick --> experience
    logistics --> budget
    experience --> budget
    budget -- "over budget, cut travel or hotel" --> logistics
    budget -- "over budget, cut activities" --> experience
    budget -- "ok or best_effort" --> writer
    writer --> wait
```

Use two plain edges into `budget` (`logistics -> budget` and `experience -> budget`), not the list form `add_edge(["logistics", "experience"], "budget")`. The list form waits for both nodes, so the retry loop stalls the first time only one of them re-runs. This was checked on LangGraph 1.2.
