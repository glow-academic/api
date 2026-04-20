"""TTS dispatch executor — one-shot text → audio via litellm /audio/speech.

Takes the dispatch's last user-role instruction as input text, calls the
configured TTS model, writes the audio bytes to the upload store, and
emits ``generate_audio_complete`` with the ``upload_id`` so downstream
handlers can attach it to an entry.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.generation.emit import emit_modality_event
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.globals import UPLOAD_FOLDER, get_pool
from app.infra.upload_paths import ensure_upload_subdir
from app.infra.websocket.generation_types import GenerateErrorApiRequest
from app.infra.websocket.socket_event import EmitFn
from app.tools.entries.uploads.create import create_upload

try:
    import litellm  # type: ignore

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


def _extract_prompt(dispatch: AgentDispatch) -> str:
    """Pull the text to synthesize out of the dispatch messages."""
    for msg in reversed(dispatch.messages or []):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user":
            content = msg.get("content") or ""
            if content:
                return content
    # Fall back to the very last message content if no user turn exists.
    if dispatch.messages:
        last = dispatch.messages[-1]
        if isinstance(last, dict):
            return last.get("content") or ""
    return ""


async def _write_audio_upload(
    session_id: UUID,
    audio_bytes: bytes,
    *,
    pool: Any,
    upload_folder: Path = UPLOAD_FOLDER,
    mime_type: str = "audio/mpeg",
    extension: str = "mp3",
) -> UUID:
    folder = ensure_upload_subdir("audio", upload_folder=upload_folder)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}.{extension}"
    relative_path = f"audio/{filename}"
    (folder / filename).write_bytes(audio_bytes)
    async with pool.acquire() as conn:
        upload = await create_upload(
            conn,
            session_id=session_id,
            file_path=relative_path,
            mime_type=mime_type,
            size=len(audio_bytes),
        )
    return upload.id


async def execute_tts_dispatch(
    *,
    dispatch: AgentDispatch,
    prepared: PrepareGenerationResult,
    sid: str,
    emit: EmitFn,
) -> None:
    """Synthesize audio from the dispatch's input text and emit the result."""
    artifact_type = prepared.artifact_type
    group_id = str(prepared.group_id)
    run_id = str(prepared.run_id)
    session_id = prepared.session_id
    resource_type = dispatch.resource_types[0] if dispatch.resource_types else artifact_type

    if not LITELLM_AVAILABLE:
        await emit_modality_event(
            emit, "audio", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message="TTS unavailable: litellm not installed",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    llm_config = dispatch.llm_config
    api_key = llm_config.get("api_key")
    if not api_key:
        await emit_modality_event(
            emit, "audio", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message="No API key configured for TTS",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    prompt = _extract_prompt(dispatch)
    if not prompt:
        await emit_modality_event(
            emit, "audio", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message="TTS requires input text (instructions)",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    voice = llm_config.get("voice") or "alloy"
    model = llm_config.get("model")
    base_url = llm_config.get("base_url")

    try:
        response = await litellm.aspeech(  # type: ignore[attr-defined]
            model=model,
            input=prompt,
            voice=voice,
            api_key=api_key,
            api_base=base_url,
        )
        # litellm returns an OpenAI-compatible object; .content is the bytes.
        audio_bytes: bytes = (
            response.content if hasattr(response, "content") else bytes(response)
        )
    except Exception as exc:
        await emit_modality_event(
            emit, "audio", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=f"TTS failed: {exc}",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    try:
        upload_id = await _write_audio_upload(
            session_id, audio_bytes, pool=get_pool(),
        )
    except Exception as exc:
        await emit_modality_event(
            emit, "audio", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=f"Failed to persist TTS audio: {exc}",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    await emit_modality_event(
        emit, "audio", "complete",
        {
            "modality": "audio",
            "sid": sid,
            "artifact_type": artifact_type,
            "resource_type": resource_type,
            "run_id": run_id,
            "group_id": group_id,
            "type": "complete",
            "event_type": "audio_complete",
            "upload_id": str(upload_id),
            "file_size": len(audio_bytes),
            "mime_type": "audio/mpeg",
            "metadata": dispatch.metadata or None,
        }, artifact_type=artifact_type,
        )


__all__ = ["execute_tts_dispatch"]
