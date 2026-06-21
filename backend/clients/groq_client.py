import os

import instructor
from groq import Groq

from backend.clients.retry_policy import MAX_RETRIES

DEFAULT_MODEL = "llama-3.3-70b-versatile"


def get_instructor_client() -> instructor.Instructor:
    """Returns a Groq client patched by Instructor for structured-output extraction.

    Used for the classification call and per-stance/judge debate calls. The pure
    routing logic in backend/routing must never import this module.
    """
    api_key = os.environ["GROQ_API_KEY"]
    raw_client = Groq(api_key=api_key)
    return instructor.from_groq(raw_client, mode=instructor.Mode.JSON, max_retries=MAX_RETRIES)
