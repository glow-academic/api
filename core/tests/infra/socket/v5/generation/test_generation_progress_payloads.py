"""Tests for pure payload helpers in generation_progress_impl."""

from app.infra.websocket.generation_progress_impl import (
    build_generation_progress_payload,
    resolve_generation_progress_target,
)


def test_resolve_generation_progress_target_prefers_resource_result():
    target_type, target_name, result_id = resolve_generation_progress_target(
        {
            "resource_type": "fallback-resource",
            "result": {
                "resource_id": "resource-1",
                "resource_type": "document",
                "entry_id": "entry-1",
                "entry_type": "summary",
            },
        }
    )

    assert (target_type, target_name, result_id) == (
        "resource",
        "document",
        "resource-1",
    )


def test_resolve_generation_progress_target_uses_entry_when_resource_missing():
    target_type, target_name, result_id = resolve_generation_progress_target(
        {
            "result": {
                "entry_id": "entry-1",
                "entry_type": "summary",
            },
        }
    )

    assert (target_type, target_name, result_id) == (
        "entry",
        "summary",
        "entry-1",
    )


def test_build_generation_progress_payload_caps_percentage_at_100():
    payload = build_generation_progress_payload(
        {
            "sid": "sid-1",
            "artifact_type": "document",
            "group_id": "group-1",
            "run_id": "run-1",
        },
        completed=3,
        total=2,
        last_completed_resource="document",
    )

    assert payload == {
        "type": "progress",
        "sid": "sid-1",
        "artifact_type": "document",
        "group_id": "group-1",
        "run_id": "run-1",
        "completed_resources": 3,
        "total_resources": 2,
        "percentage": 100,
        "last_completed_resource": "document",
    }


def test_build_generation_progress_payload_handles_zero_total():
    payload = build_generation_progress_payload(
        {
            "sid": "sid-1",
            "run_id": "run-1",
        },
        completed=0,
        total=0,
        last_completed_resource="entry",
    )

    assert payload["percentage"] == 0
    assert payload["artifact_type"] == "unknown"
    assert payload["last_completed_resource"] == "entry"
