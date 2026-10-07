"""Runs app.py headlessly with a fake model, so no API key or network is needed."""

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import SystemMessage
from streamlit.testing.v1 import AppTest

import planner.llm

APP = "../app.py"
TIMEOUT = 30  # the first run imports LangChain, which can take longer than AppTest's 3 s default


class RecordingModel(FakeListChatModel):
    """Fake model that keeps the messages it was sent on each call."""

    calls: list = []

    def _stream(self, messages, *args, **kwargs):
        self.calls.append(messages)
        return super()._stream(messages, *args, **kwargs)


class FailingModel(FakeListChatModel):
    def _stream(self, *args, **kwargs):
        raise TimeoutError("model timed out")


def test_chat_round_trip(monkeypatch):
    monkeypatch.setattr(planner.llm, "get_llm", lambda: FakeListChatModel(responses=["Waves it is!"]))

    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    assert at.chat_message[0].markdown[0].value.startswith("Hi!")

    at.chat_input[0].set_value("Waves, definitely").run()
    assert not at.exception
    assert at.chat_message[-1].markdown[0].value == "Waves it is!"
    assert len(at.session_state.messages) == 3


def test_model_error_drops_message_and_allows_retry(monkeypatch):
    monkeypatch.setattr(planner.llm, "get_llm", lambda: FailingModel(responses=[""]))

    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    at.chat_input[0].set_value("Hills please").run()

    assert not at.exception
    assert "The model call failed" in at.error[0].value
    assert len(at.session_state.messages) == 1  # only the greeting is left

    monkeypatch.setattr(planner.llm, "get_llm", lambda: FakeListChatModel(responses=["Hills it is!"]))
    at.chat_input[0].set_value("Hills please").run()
    assert not at.exception
    assert at.chat_message[-1].markdown[0].value == "Hills it is!"
    assert len(at.session_state.messages) == 3


def test_only_recent_history_is_sent(monkeypatch):
    model = RecordingModel(responses=["ok"], calls=[])
    monkeypatch.setattr(planner.llm, "get_llm", lambda: model)

    at = AppTest.from_file(APP, default_timeout=TIMEOUT).run()
    for i in range(12):  # greeting + 12 user turns + 12 replies = 25 messages before the last call
        at.chat_input[0].set_value(f"answer {i}").run()

    assert not at.exception
    sent = model.calls[-1]
    assert isinstance(sent[0], SystemMessage)
    assert len(sent) == 1 + planner.llm.MAX_HISTORY
    assert sent[-1].content == "answer 11"


def test_llm_client_settings(monkeypatch):
    secrets = {"LLM_BASE_URL": "https://router.example/v1", "HF_TOKEN": "test-token", "LLM_MODEL": "test-model"}
    monkeypatch.setattr(planner.llm.st, "secrets", secrets)
    planner.llm.get_llm.clear()

    llm = planner.llm.get_llm()

    assert llm.model_name == "test-model"
    assert llm.openai_api_base == "https://router.example/v1"
    assert llm.request_timeout == 60
    assert llm.max_retries == 2
    assert llm.streaming and llm.stream_usage
    assert planner.llm.get_llm() is llm  # cached per process
    planner.llm.get_llm.clear()
