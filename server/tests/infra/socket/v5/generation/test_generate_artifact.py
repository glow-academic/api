"""Tests for generate_artifact_impl — EmitFn pattern.

Token factory: streams model outputs, executes tools, emits events.
Uses recording_emit() to capture events.
"""

from __future__ import annotations

import pytest

from app.infra.websocket.generate_artifact_impl import generate_artifact_impl
from app.infra.websocket.generation_types import GenerateArtifactPayload, ModelConfig
from app.infra.websocket.socket_event import recording_emit


def _model_config(**overrides: object) -> ModelConfig:
    defaults = {
        "model": "gpt-4o",
        "api_key": None,
        "base_url": "https://api.openai.com",
        "temperature": 0.7,
        "reasoning": None,
        "provider": "openai",
        "voice": None,
        "quality": None,
        "length_seconds": None,
        "response_format": None,
        "tool_choice": "required",
        "extra_body": None,
    }
    defaults.update(overrides)
    return ModelConfig(**defaults)


def _payload(**overrides: object) -> GenerateArtifactPayload:
    defaults: dict = {
        "sid": "s1",
        "run_id": "run-1",
        "group_id": "grp-1",
        "artifact_type": "agent",
        "resource_type": "names",
        "modality": "call",
        "messages": [{"role": "user", "content": "Hello"}],
        "llm_config": _model_config(),
        "tools": None,
        "metadata": None,
        "profile_id": "00000000-0000-0000-0000-000000000001",
        "profiles_id": "00000000-0000-0000-0000-000000000002",
        "session_id": "00000000-0000-0000-0000-000000000003",
    }
    defaults.update(overrides)
    return GenerateArtifactPayload(**defaults)


@pytest.mark.asyncio
class TestGenerateArtifactImpl:
    # ------------------------------------------------------------------
    # Media passthrough
    # ------------------------------------------------------------------

    async def test_image_passthrough_emits_start_and_complete(self):
        """Pre-uploaded image file emits start + complete (no LLM call)."""
        emit, events = recording_emit()
        payload = _payload(
            modality="image",
            file_path="/uploads/img.png",
            mime_type="image/png",
            file_size=1234,
            upload_id="up-1",
        )
        await generate_artifact_impl(payload, emit=emit, sid="s1", profile_id=None)
        names = [e.event for e in events]
        assert "generate_image_start" in names
        assert "generate_image_complete" in names
        complete = next(e for e in events if e.event == "generate_image_complete")
        assert complete.data["file_path"] == "/uploads/img.png"

    async def test_video_passthrough_emits_start_and_complete(self):
        emit, events = recording_emit()
        payload = _payload(
            modality="video",
            file_path="/uploads/vid.mp4",
            mime_type="video/mp4",
            file_size=5678,
            upload_id="up-2",
        )
        await generate_artifact_impl(payload, emit=emit, sid="s1", profile_id=None)
        names = [e.event for e in events]
        assert "generate_video_start" in names
        assert "generate_video_complete" in names

    # ------------------------------------------------------------------
    # Media generation via adapter
    # ------------------------------------------------------------------

    async def test_image_generation_calls_adapter(self):
        """AI-generated image dispatches to media adapter."""
        emit, events = recording_emit()
        payload = _payload(modality="image")  # no file_path → adapter path
        calls: list[dict] = []

        class FakeMediaAdapter:
            async def generate(self, **kwargs) -> None:
                calls.append(kwargs)

        await generate_artifact_impl(
            payload,
            emit=emit,
            sid="s1",
            profile_id=None,
            get_media_adapter_fn=lambda: FakeMediaAdapter(),
        )
        assert len(calls) == 1
        assert calls[0]["modality"] == "image"
        # Should still emit start
        assert any(e.event == "generate_image_start" for e in events)

    async def test_image_generation_error_emits_error(self):
        emit, events = recording_emit()
        payload = _payload(modality="image")

        class FakeMediaAdapter:
            async def generate(self, **kwargs) -> None:
                raise RuntimeError("GPU OOM")

        await generate_artifact_impl(
            payload,
            emit=emit,
            sid="s1",
            profile_id=None,
            get_media_adapter_fn=lambda: FakeMediaAdapter(),
        )
        error_events = [e for e in events if e.event == "generate_image_error"]
        assert len(error_events) == 1
        assert "GPU OOM" in error_events[0].data["error_message"]

    # ------------------------------------------------------------------
    # Audio setup
    # ------------------------------------------------------------------

    async def test_audio_no_api_key_emits_error(self):
        emit, events = recording_emit()
        payload = _payload(modality="audio", llm_config=_model_config(api_key=None))
        await generate_artifact_impl(payload, emit=emit, sid="s1", profile_id=None)
        error_events = [e for e in events if e.event == "generate_audio_error"]
        assert len(error_events) == 1
        assert "No API key" in error_events[0].data["error_message"]

    async def test_audio_session_init_failure_emits_error(self):
        emit, events = recording_emit()
        payload = _payload(
            modality="audio",
            llm_config=_model_config(api_key="enc-key"),
        )
        removed: list[str] = []

        class FakeAudioAdapter:
            async def initialize_session(self, **kwargs) -> None:
                raise RuntimeError("ws failed")

        class FakeSession:
            tool_output_schemas: dict[str, dict[str, str]] = {}

        await generate_artifact_impl(
            payload,
            emit=emit,
            sid="s1",
            profile_id=None,
            decrypt_api_key_fn=lambda encrypted: "sk-test",
            get_audio_adapter_fn=lambda: FakeAudioAdapter(),
            create_session_fn=lambda **kwargs: FakeSession(),
            remove_session_fn=lambda group_id: removed.append(group_id),
        )
        error_events = [e for e in events if e.event == "generate_audio_error"]
        assert len(error_events) == 1
        assert "voice service" in error_events[0].data["error_message"]
        assert removed == ["grp-1"]

    async def test_audio_session_success_emits_session_start(self):
        emit, events = recording_emit()
        payload = _payload(
            modality="audio",
            llm_config=_model_config(api_key="enc-key"),
        )

        class FakeAudioAdapter:
            async def initialize_session(self, **kwargs) -> None:
                return None

        class FakeSession:
            tool_output_schemas: dict[str, dict[str, str]] = {}

        await generate_artifact_impl(
            payload,
            emit=emit,
            sid="s1",
            profile_id=None,
            decrypt_api_key_fn=lambda encrypted: "sk-test",
            get_audio_adapter_fn=lambda: FakeAudioAdapter(),
            create_session_fn=lambda **kwargs: FakeSession(),
            remove_session_fn=lambda group_id: None,
        )
        session_events = [
            e for e in events if e.event == "generate_audio_session_start"
        ]
        assert len(session_events) == 1
        assert session_events[0].data["message"] == "Audio session ready"

    # ------------------------------------------------------------------
    # Unsupported modality
    # ------------------------------------------------------------------

    async def test_unsupported_modality_emits_generate_error(self):
        """Unknown modality falls back to generate_error event."""
        emit, events = recording_emit()
        payload = _payload(modality="hologram")

        # The start event will go to generate_error since "hologram" is not supported
        # Then it will enter the agentic loop and fail (no litellm)
        # We just need to verify the fallback behavior
        await generate_artifact_impl(payload, emit=emit, sid="s1", profile_id=None)
        error_events = [e for e in events if e.event == "generate_error"]
        assert len(error_events) >= 1

    # ------------------------------------------------------------------
    # Agentic loop — basic flow
    # ------------------------------------------------------------------

    async def test_agentic_loop_no_tools_emits_run_complete(self):
        """Simple text generation with no tools → start + text events + run_complete."""
        emit, events = recording_emit()
        payload = _payload(modality="call")

        # Mock stream_litellm_events to yield text_start, text_delta, text_complete, message_complete
        mock_events = [
            {"type": "text_start"},
            {"type": "text_delta", "delta": "Hello "},
            {"type": "text_delta", "delta": "world"},
            {"type": "text_complete", "text": "Hello world"},
            {
                "type": "message_complete",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        ]

        async def fake_stream_events(stream):
            for ev in mock_events:
                yield ev

        async def fake_call_chat_completions_api(**kwargs):
            return object()

        async def fake_call_responses_api(**kwargs):
            raise RuntimeError("responses unavailable")

        await generate_artifact_impl(
            payload,
            emit=emit,
            sid="s1",
            profile_id=None,
            call_responses_api_fn=fake_call_responses_api,
            call_chat_completions_api_fn=fake_call_chat_completions_api,
            stream_litellm_events_fn=fake_stream_events,
        )

        event_names = [e.event for e in events]
        assert "generate_call_start" in event_names
        assert "generate_text_start" in event_names
        assert "generate_text_progress" in event_names
        assert "generate_text_complete" in event_names
        assert "generate_run_complete" in event_names

        run_complete = next(e for e in events if e.event == "generate_run_complete")
        assert run_complete.data["assistant_output"] == "Hello world"
        assert run_complete.data["input_text_tokens"] == 10
        assert run_complete.data["output_text_tokens"] == 5

    async def test_agentic_loop_llm_error_emits_error(self):
        """LLM call failure emits token factory error."""
        emit, events = recording_emit()
        payload = _payload(modality="call")

        async def fake_call_chat_completions_api(**kwargs):
            raise RuntimeError("API timeout")

        async def fake_call_responses_api(**kwargs):
            raise RuntimeError("responses unavailable")

        await generate_artifact_impl(
            payload,
            emit=emit,
            sid="s1",
            profile_id=None,
            call_responses_api_fn=fake_call_responses_api,
            call_chat_completions_api_fn=fake_call_chat_completions_api,
        )

        error_events = [e for e in events if e.event == "generate_call_error"]
        assert len(error_events) == 1
        assert "Token factory error" in error_events[0].data["error_message"]
