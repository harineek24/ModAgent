import math

from pydantic import BaseModel, Field, field_validator

from backend.models.category import Category


class ClassificationResult(BaseModel):
    scores: dict[Category, float]
    detected_language: str
    flags: list[str] = Field(default_factory=list)

    @field_validator("scores")
    @classmethod
    def validate_score_range(cls, scores: dict[Category, float]) -> dict[Category, float]:
        for category, score in scores.items():
            if math.isnan(score) or not 0.0 <= score <= 1.0:
                raise ValueError(f"score for {category} must be within [0.0, 1.0], got {score}")
        return scores
