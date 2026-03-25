"""Tests for generation resource normalization."""

from uuid import UUID

from app.infra.generation.resource_utils import normalize_resources_for_sql


def test_normalize_resources_for_sql_filters_invalid_ids_and_empty_entries():
    result = normalize_resources_for_sql(
        [
            {
                "resource_type": "documents",
                "resource_ids": [
                    "00000000-0000-0000-0000-000000000001",
                    "not-a-uuid",
                ],
            },
            {
                "resource_type": "images",
                "resource_ids": [],
            },
            {
                "resource_type": None,
                "resource_ids": ["00000000-0000-0000-0000-000000000002"],
            },
        ]
    )

    assert result == [
        (
            "documents",
            [UUID("00000000-0000-0000-0000-000000000001")],
        )
    ]


def test_normalize_resources_for_sql_returns_none_for_empty_input():
    assert normalize_resources_for_sql(None) is None
    assert normalize_resources_for_sql([]) is None
