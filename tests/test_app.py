"""Runs app.py headlessly with a fake model and an in-memory checkpointer.

No API key, network or database is needed. `get_llm` and `get_checkpointer` are
swapped for fakes, which works because app.py imports them fresh on each run.
"""

import uuid

import pytest
import streamlit as st
from langgraph.checkpoint.memory import InMemorySaver
from streamlit.testing.v1 import AppTest

import planner.db
import planner.llm
from tests.fakes import FakeChat, FlakyModel

APP = "../app.py"
TIMEOUT = 30  # the first run imports LangChain, which can take longer than AppTest's 3 s default


@pytest.fixture(autouse=True)
def fresh_resources(monkeypatch):
    """Clear Streamlit's cache_resource around every test.

    app.py caches the compiled graph per process. Without clearing it, the
    graph built with one test's fake model would leak into the next test.
    """
    st.cache_resource.clear()
    saver = InMemorySaver()
    monkeypatch.setattr(planner.db, "get_checkpointer", lambda: saver)
    yield saver
    st.cache_resource.clear()


def use_model(monkeypatch, model):
    monkeypatch.setattr(planner.llm, "get_llm", lambda: model)


def open_app(trip_id=None):
    at = AppTest.from_file(APP, default_timeout=TIMEOUT)
    if trip_id:
        at.query_params["trip"] = trip_id
    return at.run()


def test_new_trip_gets_id_in_url_and_greeting(monkeypatch):
    use_model(monkeypatch, FakeChat(responses=["unused"]))
    at = open_app()

    assert not at.exception
    uuid.UUID(at.query_params["trip"])  # a valid UUID was put in the URL
    assert at.chat_message[0].markdown[0].value.startswith("Hi!")


def test_chat_round_trip(monkeypatch):
    use_model(monkeypatch, FakeChat(responses=["Waves it is!"]))
    at = open_app()

    at.chat_input[0].set_value("Waves, definitely").run()

    assert not at.exception
    assert at.chat_message[-1].markdown[0].value == "Waves it is!"


def test_reopening_the_link_restores_the_conversation(monkeypatch):
    use_model(monkeypatch, FakeChat(responses=["Waves it is!"]))
    first = open_app()
    trip_id = first.query_params["trip"]
    first.chat_input[0].set_value("Waves, definitely").run()

    # A new AppTest is a new browser session: no st.session_state carried over.
    second = open_app(trip_id)

    texts = [m.markdown[0].value for m in second.chat_message]
    assert texts[1:] == ["Waves, definitely", "Waves it is!"]


def test_invalid_trip_id_starts_a_new_trip(monkeypatch):
    use_model(monkeypatch, FakeChat(responses=["unused"]))
    at = open_app("not-a-uuid")

    assert not at.exception
    assert at.query_params["trip"] != "not-a-uuid"
    uuid.UUID(at.query_params["trip"])


def test_model_error_shows_retry_and_retry_recovers(monkeypatch):
    use_model(monkeypatch, FlakyModel(responses=["Hills it is!"], fail_times=1))
    at = open_app()

    at.chat_input[0].set_value("Hills please").run()

    assert not at.exception
    assert "Something went wrong" in at.error[0].value
    assert len(at.chat_input) == 0  # nothing to type into until the run is retried
    retry = next(b for b in at.button if b.label == "Retry")

    retry.click().run()

    assert not at.exception
    assert not at.error
    assert at.chat_message[-1].markdown[0].value == "Hills it is!"
    assert len(at.chat_input) == 1


def test_new_trip_button_switches_trip(monkeypatch):
    use_model(monkeypatch, FakeChat(responses=["Waves it is!"]))
    at = open_app()
    old_id = at.query_params["trip"]
    at.chat_input[0].set_value("Waves").run()

    next(b for b in at.sidebar.button if b.label == "New trip").click().run()

    assert at.query_params["trip"] != old_id
    assert len(at.chat_message) == 1  # just the greeting


def test_database_down_shows_friendly_error(monkeypatch):
    use_model(monkeypatch, FakeChat(responses=["unused"]))

    def broken():
        raise ConnectionError("could not connect to server")

    monkeypatch.setattr(planner.db, "get_checkpointer", broken)
    at = open_app()

    assert not at.exception
    assert "can't reach the trip database" in at.error[0].value
    assert "could not connect" not in at.error[0].value  # internals not shown


def test_llm_client_settings(monkeypatch):
    secrets = {"LLM_BASE_URL": "https://router.example/v1", "LLM_API_KEY": "test-token", "LLM_MODEL": "test-model"}
    monkeypatch.setattr(planner.llm.st, "secrets", secrets)

    llm = planner.llm.get_llm()

    assert llm.model_name == "test-model"
    assert llm.openai_api_base == "https://router.example/v1"
    assert llm.openai_api_key.get_secret_value() == "test-token"  # read from LLM_API_KEY
    assert llm.request_timeout == 60
    assert llm.max_retries == 2
    assert llm.streaming and llm.stream_usage
    assert planner.llm.get_llm() is llm  # cached per process
