"""Maps OpenAI moderation eval category labels onto our internal Category enum.

Used when importing public labeled datasets into tests/golden/moderation_cases.json
so the mapping is reproducible rather than a one-time manual relabel.

CSAE-adjacent ("sexual/minors") and terrorism/extremism are intentionally excluded
from automatic import -- those golden cases should be hand-written synthetic
examples that exercise hard-route behavior, not real-world positive examples.
"""

from backend.models.category import Category

OPENAI_TO_INTERNAL = {
    "hate": Category.HATE_SPEECH,
    "hate/threatening": Category.HATE_SPEECH,
    "harassment": Category.HARASSMENT_BULLYING,
    "harassment/threatening": Category.HARASSMENT_BULLYING,
    "violence": Category.GRAPHIC_VIOLENCE,
    "violence/graphic": Category.GRAPHIC_VIOLENCE,
    "sexual": Category.SEXUAL_CONTENT_ADULT,
    "self-harm": Category.SELF_HARM_SUICIDE,
    "self-harm/intent": Category.SELF_HARM_SUICIDE,
    "self-harm/instructions": Category.SELF_HARM_SUICIDE,
}

EXCLUDED_FROM_AUTO_IMPORT = {"sexual/minors"}
