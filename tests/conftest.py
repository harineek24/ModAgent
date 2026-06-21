import pytest

from backend.models.category import Category
from backend.models.classification import ClassificationResult
from backend.routing.policy_loader import load_policy_table


@pytest.fixture
def policy_table():
    return load_policy_table()


@pytest.fixture
def benign_classification():
    return ClassificationResult(
        scores={category: 0.0 for category in Category},
        detected_language="en",
        flags=[],
    )


def make_classification(category: Category, score: float, **kwargs) -> ClassificationResult:
    scores = {c: 0.0 for c in Category}
    scores[category] = score
    return ClassificationResult(
        scores=scores,
        detected_language=kwargs.pop("detected_language", "en"),
        flags=kwargs.pop("flags", []),
    )
