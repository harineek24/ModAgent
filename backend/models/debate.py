from pydantic import BaseModel, Field

from backend.models.category import Category


class DebateTurn(BaseModel):
    stance: str
    position: str
    confidence: float
    rationale: str
    cited_clauses: list[str] = Field(default_factory=list)


class Verdict(BaseModel):
    category: Category
    decision: str
    confidence: float
    rationale: str
    cited_clauses: list[str] = Field(default_factory=list)
    escalated: bool = False


class DebateTranscript(BaseModel):
    category: Category
    advocate_turns: list[DebateTurn] = Field(default_factory=list)
    enforcer_turns: list[DebateTurn] = Field(default_factory=list)


class ModerationResult(BaseModel):
    verdicts: list[Verdict] = Field(default_factory=list)
    transcripts: list[DebateTranscript] = Field(default_factory=list)

    def transcript_for(self, category: Category) -> DebateTranscript | None:
        return next((t for t in self.transcripts if t.category == category), None)
