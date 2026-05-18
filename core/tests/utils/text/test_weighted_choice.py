"""Tests for app.utils.text.weighted_choice."""

import random

from app.utils.text.weighted_choice import weighted_choice


def test_empty_list_returns_none():
    """Empty input returns None."""
    assert weighted_choice([]) is None


def test_all_zero_weights_returns_none():
    """All-zero weights returns None."""
    assert weighted_choice([("a", 0.0), ("b", 0.0)]) is None


def test_single_item_always_chosen():
    """Single item with positive weight is always returned."""
    assert weighted_choice([("only", 1.0)]) == "only"


def test_negative_weights_treated_as_zero():
    """Negative weights are clamped to zero; only positive-weight items chosen."""
    for _ in range(50):
        result = weighted_choice([("bad", -5.0), ("good", 1.0)])
        assert result == "good"


def test_heavily_weighted_item_dominates():
    """An item with overwhelmingly large weight is almost always chosen."""
    random.seed(42)
    results = [
        weighted_choice([("rare", 0.001), ("common", 1000.0)]) for _ in range(200)
    ]
    assert results.count("common") > 190


def test_all_negative_weights_returns_none():
    """All negative weights means total <= 0, returns None."""
    assert weighted_choice([("a", -1.0), ("b", -2.0)]) is None
