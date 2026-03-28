"""Tests for app.utils.text.weighted_sample_without_replacement."""

from app.utils.text.weighted_sample_without_replacement import (
    weighted_sample_without_replacement,
)


def test_returns_correct_count():
    """Requesting k items returns exactly k when pool is large enough."""
    items = ["a", "b", "c", "d"]
    scores = [1.0, 1.0, 1.0, 1.0]
    result = weighted_sample_without_replacement(items, scores, 2)
    assert len(result) == 2


def test_no_duplicates():
    """Sampled items are unique (without replacement)."""
    items = list(range(10))
    scores = [1.0] * 10
    result = weighted_sample_without_replacement(items, scores, 5)
    assert len(result) == len(set(result))


def test_k_larger_than_pool():
    """If k > len(items), returns all items."""
    items = ["a", "b"]
    scores = [1.0, 1.0]
    result = weighted_sample_without_replacement(items, scores, 10)
    assert len(result) == 2
    assert set(result) == {"a", "b"}


def test_zero_scores_still_returns_items():
    """When all scores are zero, falls back to uniform random."""
    items = ["x", "y", "z"]
    scores = [0.0, 0.0, 0.0]
    result = weighted_sample_without_replacement(items, scores, 2)
    assert len(result) == 2
    assert all(item in items for item in result)


def test_empty_items():
    """Empty item list returns empty list."""
    result = weighted_sample_without_replacement([], [], 5)
    assert result == []


def test_original_list_not_mutated():
    """The original items list should not be modified."""
    items = ["a", "b", "c"]
    scores = [1.0, 2.0, 3.0]
    items_copy = items.copy()
    weighted_sample_without_replacement(items, scores, 2)
    assert items == items_copy
