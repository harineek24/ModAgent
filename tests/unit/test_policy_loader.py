import pytest

from backend.models.category import Category, SeverityTier


def test_every_category_has_a_policy_row(policy_table):
    assert set(policy_table.keys()) == set(Category)


def test_critical_categories_are_non_debatable(policy_table):
    for category, policy in policy_table.items():
        if policy.severity == SeverityTier.CRITICAL:
            assert policy.debatable is False, f"{category} is critical but debatable"


def test_every_policy_has_a_nonempty_rubric(policy_table):
    for category, policy in policy_table.items():
        assert policy.rubric.strip(), f"{category} has an empty rubric"


def test_benign_category_is_not_debatable_or_escalating(policy_table):
    benign_policy = policy_table[Category.BENIGN]
    assert benign_policy.debatable is False
    assert benign_policy.severity == SeverityTier.NONE
