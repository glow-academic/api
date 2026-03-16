"""Tests for pure helpers in generation_ended_impl."""

from app.infra.websocket.generation_ended_impl import (
    _table_name,
    build_generation_complete_payload,
    parse_generation_resolution_context,
)


def test_table_name_uses_resource_suffix_for_resources():
    assert _table_name("resource", "names") == "names_resource"


def test_table_name_uses_entry_suffix_for_non_resources():
    assert _table_name("entry", "messages") == "messages_entry"


def test_parse_generation_resolution_context_prefers_stored_values():
    parsed = parse_generation_resolution_context(
        {
            "run_id": "run-1",
            "sid": "sid-1",
            "artifact_type": "agent",
            "group_id": "group-1",
            "resource_actions": {"names": "created"},
        },
        {
            "sid": "sid-fallback",
        },
    )

    assert parsed == (
        "run-1",
        "sid-1",
        "agent",
        "group-1",
        {"names": "created"},
    )


def test_parse_generation_resolution_context_falls_back_to_request_sid_and_defaults():
    parsed = parse_generation_resolution_context(
        {},
        {
            "sid": "sid-fallback",
        },
    )

    assert parsed == (
        None,
        "sid-fallback",
        "unknown",
        "",
        {},
    )


def test_build_generation_complete_payload_serializes_completion_contract():
    payload = build_generation_complete_payload(
        sid="sid-1",
        artifact_type="document",
        group_id="group-1",
        run_id="run-1",
        resource_actions={"documents": "updated"},
    )

    assert payload == {
        "type": "complete",
        "sid": "sid-1",
        "artifact_type": "document",
        "artifact_id": None,
        "group_id": "group-1",
        "run_id": "run-1",
        "success": True,
        "message": "Document generation resolved",
        "resource_actions": {"documents": "updated"},
    }
