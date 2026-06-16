"""Image/video dispatch executor — used by the unified execute_generation.

Two sub-flows:
  1. Pre-uploaded media passthrough: if ``dispatch.file_path`` is set, emit
     ``generate_{image|video}_complete`` with the upload metadata — no model
     call is made.
  2. AI-generated media: call the media adapter (LiteLLM responses) to
     produce the asset.
"""

from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from app.infra.generation.emit import emit_modality_event
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.websocket.generation_types import (
    GenerateErrorApiRequest,
    ProducedMedia,
)
from app.infra.websocket.socket_event import EmitFn
from app.infra.server_timing import timed


def _produced_media_from(modality: str, result: Any) -> ProducedMedia | None:
    """Translate an adapter ``MediaResult`` (or a passthrough dispatch) to
    the canonical ``ProducedMedia`` we return out of execute_media_dispatch.
    """
    resource_id_str = None
    if modality == "image":
        resource_id_str = getattr(result, "images_id", None) or getattr(result, "resource_id", None)
    elif modality == "video":
        resource_id_str = getattr(result, "videos_id", None) or getattr(result, "resource_id", None)
    elif modality == "audio":
        resource_id_str = getattr(result, "audios_id", None) or getattr(result, "resource_id", None)
    upload_id_str = getattr(result, "upload_id", None)
    if not resource_id_str or not upload_id_str:
        return None
    try:
        return ProducedMedia(
            modality=modality,  # type: ignore[arg-type]
            resource_id=UUID(str(resource_id_str)),
            upload_id=UUID(str(upload_id_str)),
            mime_type=getattr(result, "mime_type", None),
            file_size=getattr(result, "file_size", None),
        )
    except (ValueError, TypeError):
        return None


async def execute_media_dispatch(
    *,
    dispatch: AgentDispatch,
    prepared: PrepareGenerationResult,
    sid: str,
    emit: EmitFn,
) -> ProducedMedia | None:
    """Generate (or passthrough) an image/video artifact.

    Returns a ``ProducedMedia`` describing the produced asset so the
    caller (``execute_generation``) can bubble it onto
    ``ArtifactGenerateResponse.produced_media``. ``None`` on error or
    when ``dispatch.file_path`` (passthrough) lacks an ``upload_id``.
    """
    outs = dispatch.output_modalities or set()
    if "image" in outs:
        modality = "image"
    elif "video" in outs:
        modality = "video"
    else:
        modality = "image"  # conservative fallback
    artifact_type = prepared.artifact_type
    group_id = str(prepared.group_id)
    run_id = str(prepared.run_id)
    # Profile room every connected client for this user joined at WS
    # connect time. Text emits in execute.py already set rooms here;
    # without this, media emits go only to ``sid`` (the originating
    # page) and any other tab/observer of the same user — including
    # the make-debug panel that joins the profile room — silently
    # misses them.
    profile_id = str(prepared.profile_id) if prepared.profile_id else ""
    resource_type = dispatch.resource_types[0] if dispatch.resource_types else artifact_type
    metadata = dispatch.metadata
    # Pre-mint the announcement message id BEFORE adapter.generate so
    # the FE listener can key its skeleton bubble by this id on the
    # ``image.start`` event, then swap in the rendered ``<img>`` when
    # ``image.complete`` arrives carrying the same id. ``media_upload_impl``
    # honors this via its ``message_id`` kwarg (passed through context).
    message_id = (
        uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.uuid4()
    )

    if dispatch.file_path:
        await emit_modality_event(
            emit,
            modality,
            "complete",
            {
                "modality": modality,
                "sid": sid,
                "rooms": [profile_id] if profile_id else [],
                "artifact_type": artifact_type,
                "type": "complete",
                "event_type": "media_complete",
                "resource_type": resource_type,
                "resource_id": dispatch.resource_id,
                "run_id": run_id,
                "group_id": group_id,
                "file_path": dispatch.file_path,
                "mime_type": dispatch.mime_type,
                "file_size": dispatch.file_size,
                "upload_id": dispatch.upload_id,
                "metadata": metadata,
            },
            artifact_type=artifact_type,
        )
        # Passthrough: emit only — dispatch.resource_id/upload_id are
        # the pre-allocated ones, sufficient to surface for download.
        passthrough_resource_id = dispatch.resource_id
        passthrough_upload_id = dispatch.upload_id
        if passthrough_resource_id and passthrough_upload_id:
            try:
                return ProducedMedia(
                    modality=modality,  # type: ignore[arg-type]
                    resource_id=UUID(str(passthrough_resource_id)),
                    upload_id=UUID(str(passthrough_upload_id)),
                    mime_type=dispatch.mime_type,
                    file_size=dispatch.file_size,
                )
            except (ValueError, TypeError):
                return None
        return None

    from app.infra.websocket.media_lifecycle import get_media_adapter

    adapter = get_media_adapter()

    prompt = ""
    if dispatch.messages:
        last = dispatch.messages[-1]
        prompt = last.get("content", "") if isinstance(last, dict) else ""

    llm_config = dispatch.llm_config
    extra_body: dict[str, Any] = {}
    for key in ("voice", "quality", "length_seconds", "response_format"):
        val = llm_config.get(key)
        if val is not None:
            extra_body[key] = val
    if llm_config.get("extra_body"):
        extra_body.update(llm_config["extra_body"])

    context = {
        "sid": sid,
        # Profile room for WS fan-out — see ``profile_id`` rationale
        # above. The adapter forwards this into every media-emit
        # payload so other tabs / observers get the events too.
        "profile_id": profile_id,
        # Caller-supplied label + derived description for the produced
        # ``{m}s_resource`` row. ``media_upload_impl`` reads these out
        # of the adapter context and resolves collisions by suffixing
        # the title with " 1", " 2", … when the bare title is taken.
        "title": prepared.title,
        "description": prepared.description,
        # ``session_id`` is the canonical session pointer threaded by
        # ``prepare_generation`` — pass it through so the adapter can
        # resolve the upload's session without needing a live socket
        # handshake (which the agentic/tool-dispatch nested path
        # doesn't have).
        "session_id": str(prepared.session_id) if prepared.session_id else None,
        "run_id": run_id,
        "group_id": group_id,
        "artifact_type": artifact_type,
        "resource_type": resource_type,
        "resource_id": dispatch.resource_id,
        # FE listener keys media skeletons by this id: ``image.start``
        # carries it, ``image.complete`` carries the same one. Same
        # value gets used as ``messages_entry.id`` inside
        # ``media_upload_impl`` so the optimistic skeleton lines up
        # with the persisted row.
        "message_id": str(message_id),
        "metadata": metadata,
    }

    try:
        with timed("model_call"):
            media_result = await adapter.generate(
                modality=modality,
                prompt=prompt,
                model=llm_config.get("model"),
                api_key=llm_config.get("api_key") or "",
                base_url=llm_config.get("base_url"),
                quality=llm_config.get("quality"),
                extra_body=extra_body or None,
                context=context,
            )
    except Exception as exc:
        await emit_modality_event(
            emit,
            modality,
            "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=f"Media generation failed: {exc}",
                artifact_type=artifact_type,
                group_id=group_id,
                resource_type=resource_type,
                resource_id=dispatch.resource_id,
            ).model_dump(),
            artifact_type=artifact_type,
        )
        # R7 parity: the modality ``.error`` event clears the FE skeleton, but
        # ``return None`` is the SUCCESS signal to ``execute_generation`` — so a
        # media failure produced a false ``.completed`` terminal + HTTP 200
        # alongside the ``.error``. Re-raise so the audit wrapper owns a single
        # ``.failed`` terminal and the route status reflects the failure.
        raise

    return _produced_media_from(modality, media_result)


__all__ = ["execute_media_dispatch"]
