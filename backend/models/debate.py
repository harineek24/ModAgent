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
