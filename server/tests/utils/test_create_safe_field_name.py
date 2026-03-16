"""Tests for create_safe_field_name."""

from app.utils.agents.create_safe_field_name import create_safe_field_name


def test_replaces_special_characters_and_spaces():
    assert (
        create_safe_field_name("Clinical Reasoning / OSCE") == "clinical_reasoning_osce"
    )


def test_collapses_and_strips_underscores():
    assert create_safe_field_name("__Score---Value__") == "score_value"
