"""Tests for extracted pure helpers in run_complete_impl."""

from app.infra.websocket.run_complete_impl import (
    _table_name,
    build_run_complete_payload,
)


def test_table_name_uses_resource_suffix():
    assert _table_name("resource", "names") == "names_resource"


def test_table_name_uses_entry_suffix():
    assert _table_name("entry", "contents") == "contents_entry"


def test_build_run_complete_payload_serializes_generation_complete_shape():
    payload = build_run_complete_payload(
        sid="sid-1",
        artifact_type="chat",
        group_id="group-1",
        run_id="run-1",
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
        "tool_results": None,
        "metadata": None,
    }
