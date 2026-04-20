"""STT dispatch executor — one-shot audio → text via litellm /audio/transcriptions.

Input is a resource-level ``audios_id``. The executor resolves it down to
the raw ``uploads_entry.file_path`` via the canonical join
(``audios_resource → audios_audios_connection → audios_entry →
audio_uploads_entry → uploads_entry``), runs transcription, and emits the
transcript via the canonical text-complete event.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.infra.generation.emit import emit_modality_event
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.globals import UPLOAD_FOLDER, get_pool
from app.infra.upload_paths import resolve_upload_path
from app.infra.websocket.generation_types import GenerateErrorApiRequest
from app.infra.websocket.socket_event import EmitFn
from app.tools.resources.audios.get import get_upload_by_audios_id

try:
    import litellm  # type: ignore

    LITELLM_AVAILABLE = True
except ImportError:
    LITELLM_AVAILABLE = False


async def execute_stt_dispatch(
    *,
    dispatch: AgentDispatch,
    prepared: PrepareGenerationResult,
    sid: str,
    emit: EmitFn,
) -> None:
    """Transcribe ``dispatch.audios_id`` and emit the text."""
    artifact_type = prepared.artifact_type
    group_id = str(prepared.group_id)
    run_id = str(prepared.run_id)
    resource_type = dispatch.resource_types[0] if dispatch.resource_types else artifact_type

    if not LITELLM_AVAILABLE:
        await emit_modality_event(
            emit, "text", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message="STT unavailable: litellm not installed",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    if not dispatch.audios_id:
        await emit_modality_event(
            emit, "text", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message="STT requires audios_id on the request",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    llm_config = dispatch.llm_config
    api_key = llm_config.get("api_key")
    if not api_key:
        await emit_modality_event(
            emit, "text", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message="No API key configured for STT",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    try:
        audios_uuid = UUID(dispatch.audios_id)
    except ValueError:
        await emit_modality_event(
            emit, "text", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=f"Invalid audios_id: {dispatch.audios_id}",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    pool = get_pool()
    async with pool.acquire() as conn:
        upload = await get_upload_by_audios_id(conn, audios_uuid)

    if upload is None:
        await emit_modality_event(
            emit, "text", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=f"No upload linked to audios_id {audios_uuid}",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    full_path = resolve_upload_path(upload.file_path, upload_folder=UPLOAD_FOLDER)

    try:
        with open(full_path, "rb") as f:
            transcription: Any = await litellm.atranscription(  # type: ignore[attr-defined]
                model=llm_config.get("model"),
                file=f,
                api_key=api_key,
                api_base=llm_config.get("base_url"),
            )
    except Exception as exc:
        await emit_modality_event(
            emit, "text", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=f"STT failed: {exc}",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        return

    text = (
        transcription.text
        if hasattr(transcription, "text")
        else str(transcription)
    )

    # Dual-emits legacy generate_text_complete + canonical
    # attempt.generate.text.complete so the client can await the canonical
    # event by group_id.
    await emit_modality_event(
        emit,
        "text",
        "complete",
        {
            "sid": sid,
            "artifact_type": artifact_type,
            "resource_type": resource_type,
            "run_id": run_id,
            "group_id": group_id,
            "type": "complete",
            "event_type": "text_complete",
            "text": text,
            "role": "assistant",
            "metadata": dispatch.metadata or None,
        },
        artifact_type=artifact_type,
    )


__all__ = ["execute_stt_dispatch"]
