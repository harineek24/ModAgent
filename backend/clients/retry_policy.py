"""Shared retry/backoff configuration for Instructor-wrapped Groq calls."""

from typing import Callable, TypeVar

import groq

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
BACKOFF_MULTIPLIER = 2.0

MAX_TOOL_USE_FAILURE_RETRIES = 2

T = TypeVar("T")


def retry_on_tool_use_failure(call: Callable[[], T]) -> T:
    """Some models occasionally hallucinate a tool call (e.g. policy_lookup) \
    even on requests where no tools were offered, which Groq rejects outright \
    as a tool_use_failed BadRequestError instead of a normal completion. \
    Instructor's own max_retries only covers response-validation failures, not \
    this provider-level rejection, so retry it here with a plain re-call.
    """
    last_error: groq.BadRequestError | None = None
    for _ in range(MAX_TOOL_USE_FAILURE_RETRIES + 1):
        try:
            return call()
        except groq.BadRequestError as error:
            last_error = error
    raise last_error
