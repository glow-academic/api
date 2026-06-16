"""STT dispatch executor — one-shot audio → text via the OpenAI SDK.

Input is a resource-level ``audios_id``. The executor resolves it down to
the raw ``uploads_entry.file_path`` via the canonical join
(``audios_resource → audios_audios_connection → audios_entry →
audio_uploads_entry → uploads_entry``), runs transcription, and emits the
transcript via the canonical text-complete event.

Why ``AsyncOpenAI`` instead of ``litellm.atranscription``: the litellm
SDK rewrites the outbound payload to ``response_format='verbose_json'``
regardless of what we pass, which is incompatible with the proxy's
upstream (``gpt-4o-transcribe`` family — supports only ``json`` / ``text``).
The OpenAI SDK pointed at the proxy's ``/v1`` base URL forwards a clean
multipart POST with our actual ``response_format``, which the proxy then
relays untouched. The chat-completion path stays on litellm because
``acompletion`` doesn't have the same kwarg-rewrite problem.
"""

from __future__ import annotations

from uuid import UUID

from openai import AsyncOpenAI

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

from app.infra.generation.emit import emit_modality_event
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.globals import UPLOAD_FOLDER, get_pool
from app.infra.upload_paths import resolve_upload_path
from app.infra.websocket.generation_types import GenerateErrorApiRequest
from app.infra.websocket.socket_event import EmitFn
from app.infra.server_timing import timed
from app.tools.resources.audios.get import get_upload_by_audios_id


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
        # R7 parity: emit the modality ``.error`` (clears the FE skeleton) then
        # RAISE — a bare ``return`` is the success signal to execute_generation,
        # so an STT failure would 200 with no transcript + a stray ``.error``.
        raise ValueError("STT requires audios_id on the request")

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
        raise ValueError("No API key configured for STT")

    base_url = llm_config.get("base_url")
    if not base_url:
        await emit_modality_event(
            emit, "text", "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message="No base_url configured for STT provider",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
        )
        raise ValueError("No base_url configured for STT provider")

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
        raise

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
        raise ValueError(f"No upload linked to audios_id {audios_uuid}")

    full_path = resolve_upload_path(upload.file_path, upload_folder=UPLOAD_FOLDER)

    # SDK-boundary URL normalization. The provider record stores the
    # bare host (``http://localhost:4000``, ``https://api.openai.com``,
    # etc.) — that's the convention our litellm-based callers in
    # ``execute.py`` / ``tts.py`` / ``media.py`` rely on, since litellm
    # appends ``/v1/<path>`` itself. The realtime adapter does the same
    # thing for its ws:// URL. ``AsyncOpenAI``, the SDK we use here, is
    # stricter: it requires ``/v1`` already on ``base_url`` and posts
    # to ``base_url/audio/transcriptions``. So we append ``/v1`` at
    # this SDK boundary. This isn't hardcoding *our* proxy — every
    # OpenAI-compatible endpoint (direct OpenAI, Azure, vLLM, etc.)
    # exposes the same ``/v1/audio/transcriptions`` shape; the
    # normalization is for the SDK, not the provider.
    proxy_base = base_url.rstrip("/")
    if not proxy_base.endswith("/v1"):
        proxy_base = f"{proxy_base}/v1"

    client = AsyncOpenAI(api_key=api_key, base_url=proxy_base)
    model_name = llm_config.get("model") or ""

    try:
        with timed("model_call"):
            with open(full_path, "rb") as f:
                transcription = await client.audio.transcriptions.create(
                    model=model_name,
                    file=f,
                    response_format="json",
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
        raise

    text = getattr(transcription, "text", None) or str(transcription)
    logger.info(
        f"VOICE_TRACE[2] stt complete: sid={sid!r} group_id={group_id} "
        f"artifact={artifact_type} text={text!r}"
    )

    # Dual-emits legacy generate_text_complete + canonical
    # attempt.generate.text.complete so the client can await the canonical
    # event by group_id.
    with timed("response_emit"):
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
            "metadata": dispatch.metadata or None,
            "rooms": [str(prepared.profile_id)],
        },
        artifact_type=artifact_type,
    )


__all__ = ["execute_stt_dispatch"]
