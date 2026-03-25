"""Tests for extracted pure payload builders in generation_events_impl."""

from app.infra.websocket.generation_events_impl import (
    _media_complete_payload,
    _media_progress_payload,
    build_generation_error_payload,
    build_grade_progress_payload,
    build_hints_payload,
    build_text_progress_payload,
)


def test_build_generation_error_payload_prefers_error_message():
    payload = build_generation_error_payload(
        {
            "sid": "s1",
            "artifact_type": "document",
            "error_message": "boom",
            "message": "ignored",
            "run_id": "run-1",
        }
    )

    assert payload["type"] == "error"
    assert payload["sid"] == "s1"
    assert payload["artifact_type"] == "document"
    assert payload["message"] == "boom"
    assert payload["run_id"] == "run-1"


def test_build_text_progress_payload_uses_chat_metadata_and_delta():
    payload = build_text_progress_payload(
        {
            "sid": "s1",
            "delta": "hello",
            "metadata": {"chat_id": "chat-1"},
        }
    )

    assert payload == {
        "sid": "s1",
        "chat_id": "chat-1",
        "content_type": "delta",
        "content": "hello",
        "audio": None,
    }


def test_build_hints_payload_defaults_to_empty_hints():
    payload = build_hints_payload(
        {
            "sid": "s1",
            "metadata": {"chat_id": "chat-1"},
            "result": {},
        }
    )

    assert payload == {
        "sid": "s1",
        "chat_id": "chat-1",
        "hints": [],
    }


def test_build_grade_progress_payload_includes_result_entry():
    payload = build_grade_progress_payload(
        {
            "sid": "s1",
            "resource_type": "rubric",
            "metadata": {"chat_id": "chat-1", "grade_id": "grade-1"},
            "result": {"score": 5},
        }
    )

    assert payload == {
        "sid": "s1",
        "chat_id": "chat-1",
        "grade_id": "grade-1",
        "resource_type": "rubric",
        "entry": {"score": 5},
    }


def test_media_progress_payload_preserves_status_message_and_metadata():
    payload = _media_progress_payload(
        {
            "sid": "s1",
            "artifact_type": "agent",
            "group_id": "group-1",
            "run_id": "run-1",
            "resource_type": "image",
            "resource_id": "resource-1",
            "metadata": {"step": 1},
        },
        modality="image",
        status="started",
        message="Image generation started",
    )

    assert payload == {
        "type": "media_progress",
        "sid": "s1",
        "modality": "image",
        "artifact_type": "agent",
        "group_id": "group-1",
        "run_id": "run-1",
        "resource_type": "image",
        "resource_id": "resource-1",
        "status": "started",
        "message": "Image generation started",
        "metadata": {"step": 1},
    }


def test_media_complete_payload_preserves_file_metadata():
    payload = _media_complete_payload(
        {
            "sid": "s1",
            "artifact_type": "agent",
            "group_id": "group-1",
            "run_id": "run-1",
            "resource_type": "video",
            "resource_id": "resource-1",
            "file_path": "/tmp/out.mp4",
            "mime_type": "video/mp4",
            "file_size": 123,
            "upload_id": "upload-1",
            "metadata": {"step": 2},
        },
        modality="video",
    )

    assert payload == {
        "type": "media_complete",
        "sid": "s1",
        "modality": "video",
        "artifact_type": "agent",
        "group_id": "group-1",
        "run_id": "run-1",
        "resource_type": "video",
        "resource_id": "resource-1",
        "file_path": "/tmp/out.mp4",
        "mime_type": "video/mp4",
        "file_size": 123,
        "upload_id": "upload-1",
        "metadata": {"step": 2},
    }
