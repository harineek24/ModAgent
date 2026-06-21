from pydantic import BaseModel

from backend.models.category import Category
from backend.models.policy import CategoryPolicy


class ContextBundle(BaseModel):
    category: Category
    policy: CategoryPolicy
    score: float


class RouterOutput(BaseModel):
    destinations: list[ContextBundle]
    hard_routed: list[ContextBundle]
    is_benign: bool
