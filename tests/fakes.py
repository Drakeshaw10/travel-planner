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
