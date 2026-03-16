"""Tests for text utility helpers."""

import random

from app.utils.text.normalize_text import normalize_text
from app.utils.text.tokenize import tokenize
from app.utils.text.weighted_choice import weighted_choice
from app.utils.text.weighted_sample_without_replacement import (
    weighted_sample_without_replacement,
)


def test_normalize_text_removes_accents_and_collapses_whitespace():
    assert normalize_text("  Café\tdu\nMONDE  ") == "cafe du monde"


def test_tokenize_returns_normalized_tokens():
    assert tokenize("  Café\tdu\nMONDE  ") == ["cafe", "du", "monde"]


def test_weighted_choice_returns_none_for_empty_or_non_positive_inputs():
    assert weighted_choice([]) is None
    assert weighted_choice([("a", 0), ("b", -1)]) is None


def test_weighted_choice_ignores_non_positive_weights():
    random.seed(7)

    assert weighted_choice([("ignored", -5), ("winner", 3), ("zero", 0)]) == "winner"


def test_weighted_sample_without_replacement_returns_unique_items():
    random.seed(11)

    result = weighted_sample_without_replacement(
        ["a", "b", "c"],
        [5, 0, -1],
        3,
    )

    assert result[0] == "a"
    assert sorted(result) == ["a", "b", "c"]
    assert len(result) == len(set(result))


def test_weighted_sample_without_replacement_limits_to_available_items():
    random.seed(3)

    result = weighted_sample_without_replacement(["a", "b"], [1, 1], 5)

    assert len(result) == 2
    assert len(set(result)) == 2
