"""Fake chat models shared by the tests. None of them use the network."""

from langchain_core.language_models.fake_chat_models import FakeListChatModel


class FlakyModel(FakeListChatModel):
    """Fails its first `fail_times` calls, then answers from `responses`.

    Used to test that a failed node leaves a checkpoint the user can retry from.
    """

    fail_times: int = 1

    def _maybe_fail(self):
        if self.fail_times > 0:
            self.fail_times -= 1
            raise TimeoutError("model timed out")

    def _call(self, *args, **kwargs):
        self._maybe_fail()
        return super()._call(*args, **kwargs)

    def _stream(self, *args, **kwargs):
        self._maybe_fail()
        return super()._stream(*args, **kwargs)


class RecordingModel(FakeListChatModel):
    """Keeps the messages it was sent on each call."""

    calls: list = []

    def _call(self, messages, *args, **kwargs):
        self.calls.append(messages)
        return super()._call(messages, *args, **kwargs)

    def _stream(self, messages, *args, **kwargs):
        self.calls.append(messages)
        return super()._stream(messages, *args, **kwargs)


class StructuredFake:
    """Stands in for a chat model in nodes that call `with_structured_output`.

    `results` is what each call returns, in order. Each one is either a model
    instance (a successful parse) or an error string (a failed parse). Calls
    return the same {"raw", "parsed", "parsing_error"} dict that LangChain
    returns with include_raw=True. Every call's messages are kept in `calls`,
    and the options passed to with_structured_output in `options`.
    """

    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self.options = {}

    def with_structured_output(self, schema, **options):
        from langchain_core.runnables import RunnableLambda

        self.options = {"schema": schema, **options}

        def respond(messages):
            self.calls.append(messages)
            result = self.results.pop(0)
            if isinstance(result, str):
                return {"raw": None, "parsed": None, "parsing_error": ValueError(result)}
            return {"raw": None, "parsed": result, "parsing_error": None}

        return RunnableLambda(respond)
