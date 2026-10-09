"""Tests for planner/llm_errors.py, using real openai error objects and the
error text Gemini actually returned on 2026-10-08 (no secrets in it)."""

from datetime import datetime, timezone

import httpx
import openai
from langchain_openai.chat_models.base import OpenAIRateLimitError

from planner.llm_errors import DAILY_QUOTA, GENERIC, PER_MINUTE, UNAVAILABLE, user_message

NOW = datetime(2026, 10, 8, 7, 0, tzinfo=timezone.utc)  # 12:30 PM IST

DAILY_TEXT = (
    "Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota, "
    "please check your plan and billing details. \\n* Quota exceeded for metric: "
    "generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, "
    "model: gemini-3.5-flash\\nPlease retry in 16h30m50.838631016s.', 'status': 'RESOURCE_EXHAUSTED', "
    "'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': "
    "[{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}, "
    "{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '59450s'}]}}]"
)
PER_MINUTE_TEXT = (
    "Error code: 429 - [{'error': {'code': 429, 'message': 'You exceeded your current quota', "
    "'details': [{'violations': [{'quotaId': 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier'}]}, "
    "{'retryDelay': '20s'}]}}]"
)


def status_error(cls, code, text):
    response = httpx.Response(code, request=httpx.Request("POST", "https://example.test/v1/chat"))
    return cls(text, response=response, body=None)


def test_daily_quota_says_when_it_comes_back_in_ist():
    msg = user_message(status_error(openai.RateLimitError, 429, DAILY_TEXT), now=NOW)
    # 07:00 UTC + 59450 s = 23:30:50 UTC = 05:00 AM IST next day, in 16 h 30 min
    assert msg == DAILY_QUOTA.format(
        when="It should be back around 05:00 AM IST (in about 16 h 30 min).")


def test_daily_quota_uses_retry_in_text_when_no_retry_delay():
    text = DAILY_TEXT.replace("'retryDelay': '59450s'", "")
    msg = user_message(status_error(openai.RateLimitError, 429, text), now=NOW)
    assert "in about 16 h 30 min" in msg


def test_daily_quota_without_any_delay_still_explains():
    text = "Error code: 429 - quotaId GenerateRequestsPerDayPerProjectPerModel-FreeTier"
    msg = user_message(status_error(openai.RateLimitError, 429, text), now=NOW)
    assert "It resets once a day." in msg


def test_langchain_wrapped_error_is_recognised():
    # What app.py actually receives: LangChain's subclass, raised "from" the original.
    original = status_error(openai.RateLimitError, 429, DAILY_TEXT)
    wrapped = status_error(OpenAIRateLimitError, 429, DAILY_TEXT)
    wrapped.__cause__ = original
    assert "today's free AI allowance" in user_message(wrapped, now=NOW)


def test_error_found_deeper_in_the_chain():
    original = status_error(openai.RateLimitError, 429, DAILY_TEXT)
    try:
        try:
            raise original
        except openai.RateLimitError as e:
            raise RuntimeError("node failed") from e
    except RuntimeError as outer:
        assert "today's free AI allowance" in user_message(outer, now=NOW)


def test_per_minute_limit_says_wait_a_minute():
    assert user_message(status_error(openai.RateLimitError, 429, PER_MINUTE_TEXT)) == PER_MINUTE


def test_no_credits_or_bad_key_says_unavailable():
    for code, cls in ((402, openai.APIStatusError), (401, openai.AuthenticationError),
                      (403, openai.PermissionDeniedError)):
        assert user_message(status_error(cls, code, "nope")) == UNAVAILABLE


def test_other_errors_stay_generic():
    assert user_message(TimeoutError("model timed out")) == GENERIC
    assert user_message(status_error(openai.InternalServerError, 503, "high demand")) == GENERIC


def test_message_never_contains_provider_details():
    msg = user_message(status_error(openai.RateLimitError, 429, DAILY_TEXT), now=NOW)
    assert "googleapis" not in msg and "quotaId" not in msg
