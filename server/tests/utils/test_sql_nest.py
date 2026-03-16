"""Tests for sql_nest helpers."""

from app.utils.sql_nest import nest, nest_row


def test_nest_row_builds_nested_dicts_from_double_underscore_keys():
    result = nest_row(
        {
            "agent__name": "Tutor",
            "agent__id": "agent-1",
            "success": True,
        }
    )

    assert result == {
        "agent": {"name": "Tutor", "id": "agent-1"},
        "success": True,
    }


def test_nest_aggregates_multi_row_collections_by_key_field():
    rows = [
        {
            "actor_name": "John",
            "agents__agent_id": "agent-1",
            "agents__agent_id__name": "Agent A",
            "agents__agent_id__status": "active",
        },
        {
            "actor_name": "John",
            "agents__agent_id": "agent-2",
            "agents__agent_id__name": "Agent B",
            "agents__agent_id__status": "idle",
        },
    ]

    result = nest(rows)

    assert result == {
        "actor_name": "John",
        "agents": {
            "agent-1": {
                "agent_id": "agent-1",
                "name": "Agent A",
                "status": "active",
            },
            "agent-2": {
                "agent_id": "agent-2",
                "name": "Agent B",
                "status": "idle",
            },
        },
    }


def test_nest_handles_scalar_fields_under_prefix_when_no_collection_exists():
    result = nest([{"theme__primary": "#000000", "theme__secondary": "#ffffff"}])

    assert result == {"theme": {"primary": "#000000", "secondary": "#ffffff"}}
