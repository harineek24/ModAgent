"""Tests for retry_on_tool_use_failure, which absorbs the case where Groq
rejects a request outright because the model hallucinated a tool call (e.g.
policy_lookup) on a request that offered no tools at all -- a provider-level
BadRequestError that Instructor's own max_retries doesn't cover.
"""

import groq
import httpx
import pytest

from backend.clients.retry_policy import MAX_TOOL_USE_FAILURE_RETRIES, retry_on_tool_use_failure


def _bad_request_error(message: str) -> groq.BadRequestError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(400, request=request)
    return groq.BadRequestError(message, response=response, body=None)


def test_returns_result_on_first_success():
    assert retry_on_tool_use_failure(lambda: "ok") == "ok"


def test_retries_then_succeeds():
    calls = {"count": 0}

    def flaky():
        calls["count"] += 1
        if calls["count"] < 2:
            raise _bad_request_error("tool_use_failed")
        return "ok"

    assert retry_on_tool_use_failure(flaky) == "ok"
    assert calls["count"] == 2


def test_raises_after_exhausting_retries():
    calls = {"count": 0}

    def always_fails():
        calls["count"] += 1
        raise _bad_request_error("tool_use_failed")

    with pytest.raises(groq.BadRequestError):
        retry_on_tool_use_failure(always_fails)
    assert calls["count"] == MAX_TOOL_USE_FAILURE_RETRIES + 1
