from typing import Literal

from pydantic import BaseModel, Field

from backend.models.category import Category

# Constrained to a fixed vocabulary so the Advocate's and Enforcer's
# positions are directly comparable -- free text ("Harmful But Contextual"
# vs. "hate speech and harassment") never matches and made every debate
# look unresolved.
Position = Literal["allow", "restrict", "escalate"]


class DebateTurn(BaseModel):
    stance: str
    position: Position
    confidence: float
    rationale: str
    cited_clauses: list[str] = Field(default_factory=list)


EscalationReason = Literal["non_debatable", "low_agreement", "judge_escalated", "agreement_escalated"] | None


class Verdict(BaseModel):
    category: Category
    decision: str
    confidence: float
    rationale: str
    cited_clauses: list[str] = Field(default_factory=list)
    escalated: bool = False
    escalation_reason: EscalationReason = None
    agreement_score: int | None = None


class AgreementCheck(BaseModel):
    """Output of the Agreement Check node: a substantive (not literal-wording)
    measure of how much the Advocate and Enforcer agree, since the Advocate's
    mandate caps out at "restrict" while the Enforcer's reaches for "escalate"
    on severe content -- meaning exact position-string matching made genuine
    agreement look like a tie.
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
