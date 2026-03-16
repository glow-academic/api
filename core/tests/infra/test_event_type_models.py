"""Tests for websocket event/data models."""

from app.infra.websocket import test_types as websocket_test_types
from app.infra.websocket.attempt_types import (
    AttemptEndedData,
    GenerateRequestData,
)
from app.infra.websocket.generation_types import (
    GenerateArtifactPayload,
    GenerateErrorApiRequest,
    GenerationErrorData,
)


def test_generate_request_data_defaults_save_and_modality():
    payload = GenerateRequestData(
        sid="sid-1",
        profile_id="profile-1",
        artifact_types=[{"name": "document", "operation": "save"}],
        artifact_id="artifact-1",
        resource_types=["documents"],
    )

    assert payload.save is True
    assert payload.modality == "call"
    assert payload.extra_messages is None


def test_attempt_ended_data_defaults_all_scenarios_complete_false():
    payload = AttemptEndedData(
        sid="sid-1",
        attempt_id="attempt-1",
        success=True,
    )

    assert payload.all_scenarios_complete is False
    assert payload.message is None


def test_generation_error_data_defaults_success_false_and_type_error():
    payload = GenerationErrorData(
        sid="sid-1",
        artifact_type="document",
        message="failed",
    )

    assert payload.type == "error"
    assert payload.success is False
    assert payload.group_id is None


def test_generate_error_api_request_allows_optional_context_fields():
    payload = GenerateErrorApiRequest(
        sid="sid-1",
        error_message="boom",
        resource_types=["documents", "images"],
    )

    assert payload.artifact_type is None
    assert payload.resource_types == ["documents", "images"]


def test_generate_artifact_payload_defaults_modality_and_timeout_fields():
    payload = GenerateArtifactPayload(
        run_id="run-1",
        messages=[{"role": "user", "content": "hello"}],
        llm_config={"model": "gpt-test"},
    )

    assert payload.modality == "text"
    assert payload.tool_timeout_seconds == 60.0
    assert payload.tools is None


def test_test_progress_and_completion_models_have_expected_defaults():
    progress = websocket_test_types.TestProgressData(invocation_id="inv-1")
    complete = websocket_test_types.TestAllCompleteEvent(
        invocation_id="inv-1", total_runs=3
    )
    error = websocket_test_types.TestErrorData(message="bad")

    assert progress.rooms == []
    assert progress.run_id is None
    assert complete.success is True
    assert error.error_type is None
