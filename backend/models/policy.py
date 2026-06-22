from pydantic import BaseModel, Field

from backend.models.category import Category, SeverityTier


class CategoryPolicy(BaseModel):
    category: Category
    severity: SeverityTier
    debatable: bool
    rubric: str
    examples: list[str] = Field(default_factory=list)
