"""TTS dispatch executor — one-shot text → audio via litellm /audio/speech.

Takes the dispatch's last user-role instruction as input text, calls the
configured TTS model, runs the canonical media-upload pipeline (uploads
→ audios_resource → audios_entry → links), emits the complete event, and
returns a ``ProducedMedia`` so the outer ``execute_generation`` bubbles
the ``audios_id`` (resource handle — the canonical plural-named public
asset id) onto ``ArtifactGenerateResponse``. Matches the image/video
path so the model gets ``produced_media`` in the tool response and can
forward the ``audios_id`` to ``Attempt_Chat_Message``.
"""

from __future__ import annotations

from uuid import UUID

from app.infra.generation.emit import emit_modality_event
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.globals import get_pool, get_redis_client
from app.infra.media.upload import media_upload_impl
from app.infra.websocket.generation_types import (
    GenerateErrorApiRequest,
    ProducedMedia,
)
from app.infra.websocket.socket_event import EmitFn
from app.infra.server_timing import timed

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


async def execute_tts_dispatch(
    *,
    dispatch: AgentDispatch,
    prepared: PrepareGenerationResult,
    sid: str,
    emit: EmitFn,
) -> ProducedMedia | None:
    """Synthesize audio from the dispatch's input text and emit the result.

    Returns a ``ProducedMedia`` carrying the freshly minted
    ``audios_resource.id`` (surfaced as ``audios_id`` to the model via
    ``ArtifactGenerateResponse.produced_media`` — canonical plural form
    matching ``images_id`` / ``videos_id``). Mirrors the image/video
    return contract so ``execute_generation`` can collect it uniformly.
    """
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
        return None

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
        return None

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
        return None

    voice = llm_config.get("voice") or "alloy"
    model = llm_config.get("model")
    base_url = llm_config.get("base_url")

    # litellm needs the ``openai/`` prefix when routing through a
    # custom proxy (api_base set) — without it the model name (e.g.
    # ``glow-audio``) is treated as an unrecognized provider and
    # ``aspeech`` errors locally before any network hop. Mirrors the
    # same prefix logic in ``execute.py:167`` / ``execute.py:205``
    # for the text-generation paths.
    effective_model = (
        f"openai/{model}" if model and base_url and "/" not in model else model
    )

    try:
        with timed("model_call"):
            response = await litellm.aspeech(  # type: ignore[attr-defined]
                model=effective_model,
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
        return None

    # Run the canonical media pipeline: writes bytes → uploads_entry →
    # audios_resource → audios_entry → audio_uploads_entry +
    # audios_audios_connection. Returns the resource id we surface as
    # ``audios_id`` (canonical plural-named public handle) so the model
    # can forward it to ``Attempt_Chat_Message``. ``attribute_to_run=False`` because the
    # tool-call audit layer writes the run↔message↔upload junction
    # itself; double-attribution would create duplicate assistant
    # messages.
    try:
      with timed("audit_write"):
        upload_result = await media_upload_impl(
            get_pool(),
            get_redis_client(),
            modality="audio",
            session_id=session_id,
            file_bytes=audio_bytes,
            filename=f"tts-{run_id}.mp3",
            content_type="audio/mpeg",
            name=(dispatch.metadata or {}).get("title") or "",
            description=prompt[:200],
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
        return None

    upload_id = upload_result.upload_id
    resource_id = upload_result.resource_id

    with timed("response_emit"):
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
            "resource_id": str(resource_id),
            "audios_id": str(resource_id),
            "file_size": upload_result.file_size,
            "mime_type": upload_result.mime_type,
            "metadata": dispatch.metadata or None,
        }, artifact_type=artifact_type,
        )

    # Bubble the produced asset onto ``ArtifactGenerateResponse.produced_media``
    # so the tool-call response template surfaces it back to the LLM as
    # the ``audios_id`` it needs for ``Attempt_Chat_Message``.
    return ProducedMedia(
        modality="audio",
        resource_id=resource_id,
        upload_id=upload_id,
        mime_type=upload_result.mime_type,
        file_size=upload_result.file_size,
    )


__all__ = ["execute_tts_dispatch"]
