"""Fake chat models shared by the tests. None of them use the network."""

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.runnables import RunnableLambda


class FakeChat(FakeListChatModel):
    """A fake model for the whole graph: chat replies *and* structured output.

    - Chat calls (the `chat` node) answer from `responses`, like FakeListChatModel.
    - `with_structured_output(Schema)` calls (profiler, constraints) answer from
      the `extractions` queue, in order. Each item is a model instance (a good
      parse) or a string (a parse error). When the queue is empty they return
      an empty `Schema()`, i.e. "the user said nothing new", so tests that only
      care about chat need no extractions at all.

    Why the queue is shared: each user turn runs at most one extracting node,
    so the order of `extractions` is simply the order of user turns.
    """

    extractions: list = []

    def with_structured_output(self, schema, **options):
        def respond(messages):
            if not self.extractions:
                return {"raw": None, "parsed": schema(), "parsing_error": None}
            result = self.extractions.pop(0)
            if isinstance(result, str):
                return {"raw": None, "parsed": None, "parsing_error": ValueError(result)}
            # Catch test mistakes early: a TripInputs queued for the profiler
            # would otherwise fail somewhere far less obvious.
            assert isinstance(result, schema), f"queued {type(result).__name__}, node asked for {schema.__name__}"
            return {"raw": None, "parsed": result, "parsing_error": None}

        return RunnableLambda(respond)


class FlakyModel(FakeChat):
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


class RecordingModel(FakeChat):
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
        self.options = {"schema": schema, **options}

        def respond(messages):
            self.calls.append(messages)
            result = self.results.pop(0)
            if isinstance(result, str):
                return {"raw": None, "parsed": None, "parsing_error": ValueError(result)}
            return {"raw": None, "parsed": result, "parsing_error": None}

        return RunnableLambda(respond)
