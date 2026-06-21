"""Single combined Groq call that scores content against every category at once.

This is the LLM boundary: it's the only place in the classification path that
talks to the network, and its sole job is to return a schema-valid
ClassificationResult via Instructor. All deterministic logic (thresholds,
hard-routing) lives downstream in backend/routing.
"""

import instructor

from backend.classification.prompts import CLASSIFIER_SYSTEM_PROMPT
from backend.clients.groq_client import DEFAULT_MODEL
from backend.clients.retry_policy import MAX_RETRIES
from backend.exceptions import ClassificationError
from backend.models.classification import ClassificationResult


def classify(client: instructor.Instructor, content: str, model: str = DEFAULT_MODEL) -> ClassificationResult:
    try:
        return client.chat.completions.create(
            model=model,
            response_model=ClassificationResult,
            max_retries=MAX_RETRIES,
            messages=[
                {"role": "system", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
        )
    except Exception as exc:
        raise ClassificationError(f"Classification failed for input: {exc}") from exc
