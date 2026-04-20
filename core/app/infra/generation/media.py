"""Image/video dispatch executor — used by the unified execute_generation.

Two sub-flows:
  1. Pre-uploaded media passthrough: if ``dispatch.file_path`` is set, emit
     ``generate_{image|video}_complete`` with the upload metadata — no model
     call is made.
  2. AI-generated media: call the media adapter (LiteLLM responses) to
     produce the asset.
"""

from __future__ import annotations

from typing import Any

from app.infra.generation.emit import emit_modality_event
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.websocket.generation_types import GenerateErrorApiRequest
from app.infra.websocket.socket_event import EmitFn


async def execute_media_dispatch(
    *,
    dispatch: AgentDispatch,
    prepared: PrepareGenerationResult,
    sid: str,
    emit: EmitFn,
) -> None:
    """Generate (or passthrough) an image/video artifact."""
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
    resource_type = dispatch.resource_types[0] if dispatch.resource_types else artifact_type
    metadata = dispatch.metadata

    if dispatch.file_path:
        await emit_modality_event(
            emit,
            modality,
            "complete",
            {
                "modality": modality,
                "sid": sid,
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
        return

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
        "run_id": run_id,
        "group_id": group_id,
        "artifact_type": artifact_type,
        "resource_type": resource_type,
        "resource_id": dispatch.resource_id,
        "metadata": metadata,
    }

    try:
        await adapter.generate(
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


__all__ = ["execute_media_dispatch"]
