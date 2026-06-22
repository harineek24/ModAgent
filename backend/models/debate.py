from typing import Literal

from pydantic import BaseModel, Field

from backend.models.category import Category

# Constrained to a fixed vocabulary so the Advocate's and Enforcer's
# positions are directly comparable -- free text ("Harmful But Contextual"
# vs. "hate speech and harassment") never matches and made every debate
# look unresolved. There is no "escalate" position: every verdict is a
# moderation decision the system stands behind, and all verdicts are shown
# to a human reviewer regardless of decision -- there's no separate
# AI-triggered escalation path to model.
Position = Literal["allow", "restrict"]


class DebateTurn(BaseModel):
    stance: str
    position: Position
    confidence: float
    rationale: str
    cited_clauses: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    category: Category
    decision: Position
    confidence: float
    rationale: str
    cited_clauses: list[str] = Field(default_factory=list)
    agreement_score: int | None = None


class AgreementCheck(BaseModel):
    """Output of the Agreement Check node: a substantive (not literal-wording)
    measure of how much the Advocate and Enforcer agree.
    """

    agreement_score: int = Field(ge=0, le=100)
    resolved_position: Position | None = None
    rationale: str


class DebateTranscript(BaseModel):
    category: Category
    advocate_turns: list[DebateTurn] = Field(default_factory=list)
    enforcer_turns: list[DebateTurn] = Field(default_factory=list)


class ModerationResult(BaseModel):
    verdicts: list[Verdict] = Field(default_factory=list)
    transcripts: list[DebateTranscript] = Field(default_factory=list)

    def transcript_for(self, category: Category) -> DebateTranscript | None:
        return next((t for t in self.transcripts if t.category == category), None)
