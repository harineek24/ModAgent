import os

import instructor
from groq import Groq

from backend.exceptions import ModAgentError

DEFAULT_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def get_instructor_client(api_key: str | None = None) -> instructor.Instructor:
    """Returns a Groq client patched by Instructor for structured-output extraction.

    api_key takes precedence over GROQ_API_KEY so a user-supplied key (e.g. typed
    into the Streamlit sidebar) can override the environment without ever being
    written to disk or config. Used for the classification call and per-stance/
    judge debate calls. The pure routing logic in backend/routing must never
    import this module.

    Retries are configured per-call via MAX_RETRIES on `.create(max_retries=...)`,
    not here -- instructor.from_groq forwards unknown kwargs straight into the
    underlying Groq client's create() call, which collides with instructor's own
    max_retries handling if passed at construction time.
    """
    resolved_key = api_key or os.environ.get("GROQ_API_KEY")
    if not resolved_key:
        raise ModAgentError("No Groq API key provided (pass api_key or set GROQ_API_KEY).")

    raw_client = Groq(api_key=resolved_key)
    return instructor.from_groq(raw_client, mode=instructor.Mode.JSON)
