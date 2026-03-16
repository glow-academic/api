"""Tests for extracted pure helpers in run_complete_impl."""

from app.infra.websocket.run_complete_impl import (
    _table_name,
    build_audio_continue_payload,
    build_generation_resolution_context,
    build_run_complete_payload,
)


def test_table_name_uses_resource_suffix():
    assert _table_name("resource", "names") == "names_resource"


def test_table_name_uses_entry_suffix():
    assert _table_name("entry", "contents") == "contents_entry"


def test_build_audio_continue_payload_uses_default_artifact_types_when_missing():
    payload = build_audio_continue_payload(
        {"metadata": {"step": 1}},
        sid="sid-1",
        artifact_type="agent",
        group_id="group-1",
        profile_id="profile-1",
        profiles_id="profiles-1",
        session_id="session-1",
    )

    assert payload == {
        "sid": "sid-1",
        "profile_id": "profile-1",
        "profiles_id": "profiles-1",
        "session_id": "session-1",
        "artifact_types": [{"name": "agent", "operation": "get"}],
        "group_id": "group-1",
        "metadata": {"step": 1},
    }


def test_build_generation_resolution_context_preserves_actions():
    payload = build_generation_resolution_context(
        sid="sid-1",
        run_id="run-1",
        artifact_type="agent",
        group_id="group-1",
        resource_actions={"names": "created"},
        entry_actions={"contents": "updated"},
    )

    assert payload == {
        "sid": "sid-1",
        "run_id": "run-1",
        "artifact_type": "agent",
        "group_id": "group-1",
        "resource_actions": {"names": "created"},
        "entry_actions": {"contents": "updated"},
    }


def test_build_run_complete_payload_serializes_generation_complete_shape():
    payload = build_run_complete_payload(
        sid="sid-1",
        artifact_type="chat",
        group_id="group-1",
        run_id="run-1",
        resource_actions={"_attempt_chat_id": "chat-1"},
    )

    assert payload == {
        "type": "complete",
        "sid": "sid-1",
        "artifact_type": "chat",
        "group_id": "group-1",
        "run_id": "run-1",
        "success": True,
        "message": "Chat generation completed",
        "artifact_id": None,
        "resource_actions": {"_attempt_chat_id": "chat-1"},
    }
