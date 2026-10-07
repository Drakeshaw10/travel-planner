"""Postgres connection pool and the LangGraph checkpointer, both on Neon.

The checkpointer is what makes trips durable: after every node, LangGraph writes
the full state for that trip (its `thread_id`) to Postgres. A sleeping,
restarted or redeployed app loses nothing, because nothing lives in memory.
"""

import streamlit as st
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


@st.cache_resource
def get_pool() -> ConnectionPool:
    """One connection pool per server process, shared by every browser session.

    Why a pool: opening a Postgres connection over TLS takes a few hundred ms.
    A pool opens a few up front and lends them out, so each graph step reuses one.
    Why `st.cache_resource`: Streamlit re-runs app.py on every click. Without the
    cache we would open a new pool, and new connections, on every rerun.
    """
    return ConnectionPool(
        conninfo=st.secrets["DATABASE_URL"],
        # Neon free tier allows few connections, and one Streamlit process
        # rarely needs more than a couple at once.
        min_size=1,
        max_size=5,
        kwargs={
            # PostgresSaver requires both: autocommit so each checkpoint write
            # is committed on its own, dict_row because it reads rows by name.
            "autocommit": True,
            "row_factory": dict_row,
            # DATABASE_URL points at Neon's *pooled* endpoint (PgBouncer in
            # transaction mode). Consecutive statements may land on different
            # server connections, so server-side prepared statements break.
            # 0 turns them off.
            "prepare_threshold": 0,
        },
        # Neon suspends the database after 5 idle minutes, which kills open
        # connections. `check` tests a connection before lending it out and
        # replaces it if it is dead, so the user sees a short pause, not an error.
        check=ConnectionPool.check_connection,
        # Recycle connections every 30 minutes, before the server drops them.
        max_lifetime=30 * 60,
        # Open the pool now, so a bad DATABASE_URL fails at startup with a clear
        # error rather than on the user's first message.
        open=True,
    )


@st.cache_resource
def get_checkpointer() -> PostgresSaver:
    """The LangGraph checkpointer, with its tables created if missing.

    `setup()` creates and migrates LangGraph's own tables (`checkpoints`,
    `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`). It is
    safe to run on every start: it only applies migrations not yet recorded.
    Never edit those tables by hand.
    """
    checkpointer = PostgresSaver(get_pool())
    checkpointer.setup()
    return checkpointer
