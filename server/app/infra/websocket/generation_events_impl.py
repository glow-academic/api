"""Generation event handlers — pure business logic with emit: EmitFn.

Small pass-through handlers for the generation pipeline events.
No socket handler registration, no module-level sio —
importable without triggering the socket tree.
"""

from __future__ import annotations

from typing import Any

from app.infra.websocket.attempt_types import (
    AttemptAssistantHintsData,
    AttemptAssistantProgressData,
    AttemptGradeProgressData,
)
from app.infra.websocket.generation_types import GenerationErrorData
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# generation_error
# ═══════════════════════════════════════════════════════════════════════════


def build_generation_error_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Build the generation_channel error payload."""
    error_message = data.get("error_message") or data.get(
        "message", "An error occurred during generation"
    )
    return GenerationErrorData(
        sid=data.get("sid", ""),
        artifact_type=data.get("artifact_type", "unknown"),
        group_id=data.get("group_id"),
        resource_type=data.get("resource_type"),
        resource_types=data.get("resource_types"),
        resource_id=data.get("resource_id"),
        run_id=data.get("run_id"),
        message=error_message,
    ).model_dump(mode="json")


def build_text_progress_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Build attempt assistant progress payload from a text delta event."""
    metadata = data.get("metadata") or {}
    return AttemptAssistantProgressData(
        sid=data.get("sid", ""),
        chat_id=metadata.get("chat_id", ""),
        content_type="delta",
        content=data.get("delta", ""),
    ).model_dump(mode="json")


def build_hints_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Build attempt assistant hints payload from a tool result."""
    metadata = data.get("metadata") or {}
    result = data.get("result") or {}
    return AttemptAssistantHintsData(
        sid=data.get("sid", ""),
        chat_id=metadata.get("chat_id", ""),
        hints=result.get("hints", []),
    ).model_dump(mode="json")


def build_grade_progress_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Build attempt grade progress payload from a tool result."""
    metadata = data.get("metadata") or {}
    result = data.get("result") or {}
    return AttemptGradeProgressData(
        sid=data.get("sid", ""),
        chat_id=metadata.get("chat_id", ""),
        grade_id=metadata.get("grade_id", ""),
        resource_type=data.get("resource_type", ""),
        entry=result,
    ).model_dump(mode="json")


async def generation_error_impl(data: dict[str, Any], *, emit: EmitFn) -> None:
    """Re-emit generation errors to generation_channel for the server layer."""
    sid = data.get("sid", "")
    if not sid:
        return

    await emit(
        [
            internal_event(
                "generation_channel",
                build_generation_error_payload(data),
            )
        ]
    )


# ═══════════════════════════════════════════════════════════════════════════
# generate_text_progress
# ═══════════════════════════════════════════════════════════════════════════


async def text_progress_impl(data: dict[str, Any], *, emit: EmitFn) -> None:
    """Handle text delta — emit attempt_assistant_progress for attempt artifacts."""
    artifact_type = data.get("artifact_type")
    if artifact_type not in ("chat", "attempt"):
        return
    metadata = data.get("metadata") or {}
    if metadata.get("grade_id"):
        return
    await emit(
        [
            internal_event(
                "attempt_assistant_progress",
                build_text_progress_payload(data),
            )
        ]
    )


# ═══════════════════════════════════════════════════════════════════════════
# generate_call_complete
# ═══════════════════════════════════════════════════════════════════════════


async def call_complete_impl(data: dict[str, Any], *, emit: EmitFn) -> None:
    """Handle tool call complete — emit attempt-specific events."""
    event_type = data.get("event_type")
    if event_type != "tool_result":
        return

    artifact_type = data.get("artifact_type")
    if artifact_type not in ("chat", "attempt"):
        return

    metadata = data.get("metadata") or {}
    sid = data.get("sid", "")

    events = []

    # Hints extraction
    if data.get("entry_type") == "hints":
        events.append(
            internal_event(
                "attempt_assistant_hints",
                build_hints_payload(data),
            )
        )

    # Grade progress (per-criterion)
    if metadata.get("grade_id"):
        events.append(
            internal_event(
                "attempt_grade_progress",
                build_grade_progress_payload(data),
            )
        )

    if events:
        await emit(events)


# ═══════════════════════════════════════════════════════════════════════════
# Media events (image/video start, progress, complete)
# ═══════════════════════════════════════════════════════════════════════════


def _media_progress_payload(
    data: dict[str, Any], *, modality: str, status: str, message: str
) -> dict[str, Any]:
    """Build a media_progress payload dict."""
    return {
        "type": "media_progress",
        "sid": data.get("sid", ""),
        "modality": modality,
        "artifact_type": data.get("artifact_type", ""),
        "group_id": data.get("group_id", ""),
        "run_id": data.get("run_id", ""),
        "resource_type": data.get("resource_type", ""),
        "resource_id": data.get("resource_id"),
        "status": status,
        "message": message,
        "metadata": data.get("metadata"),
    }


def _media_complete_payload(data: dict[str, Any], *, modality: str) -> dict[str, Any]:
    """Build a media_complete payload dict."""
    return {
        "type": "media_complete",
        "sid": data.get("sid", ""),
        "modality": modality,
        "artifact_type": data.get("artifact_type", ""),
        "group_id": data.get("group_id", ""),
        "run_id": data.get("run_id", ""),
        "resource_type": data.get("resource_type", ""),
        "resource_id": data.get("resource_id"),
        "file_path": data.get("file_path"),
        "mime_type": data.get("mime_type"),
        "file_size": data.get("file_size"),
        "upload_id": data.get("upload_id"),
        "metadata": data.get("metadata"),
    }


async def image_start_impl(data: dict[str, Any], *, emit: EmitFn) -> None:
    """Emit media progress for image generation start."""
    sid = data.get("sid", "")
    if not sid:
        return
    await emit(
        [
            internal_event(
                "generation_channel",
                _media_progress_payload(
                    data,
                    modality="image",
                    status="started",
                    message="Image generation started",
                ),
            )
        ]
    )


async def image_complete_impl(data: dict[str, Any], *, emit: EmitFn) -> None:
    """Emit media complete for image generation."""
    sid = data.get("sid", "")
    if not sid:
        return
    await emit(
        [
            internal_event(
                "generation_channel",
                _media_complete_payload(data, modality="image"),
            )
        ]
    )


async def video_start_impl(data: dict[str, Any], *, emit: EmitFn) -> None:
    """Emit media progress for video generation start."""
    sid = data.get("sid", "")
    if not sid:
        return
    await emit(
        [
            internal_event(
                "generation_channel",
                _media_progress_payload(
                    data,
                    modality="video",
                    status="started",
                    message="Video generation started",
                ),
            )
        ]
    )


async def video_progress_impl(data: dict[str, Any], *, emit: EmitFn) -> None:
    """Emit media progress for video generation polling."""
    sid = data.get("sid", "")
    if not sid:
        return
    await emit(
        [
            internal_event(
                "generation_channel",
                _media_progress_payload(
                    data,
                    modality="video",
                    status="in_progress",
                    message=data.get("message", "Video generation in progress"),
                ),
            )
        ]
    )


async def video_complete_impl(data: dict[str, Any], *, emit: EmitFn) -> None:
    """Emit media complete for video generation."""
    sid = data.get("sid", "")
    if not sid:
        return
    await emit(
        [
            internal_event(
                "generation_channel",
                _media_complete_payload(data, modality="video"),
            )
        ]
    )
