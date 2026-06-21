"""Shared retry/backoff configuration for Instructor-wrapped Groq calls."""

MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0
BACKOFF_MULTIPLIER = 2.0
