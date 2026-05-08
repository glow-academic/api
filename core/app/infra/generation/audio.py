"""Audio/realtime dispatch executor — used by the unified execute_generation.

Opens a RealtimeAudioAdapter session against the provider indicated by the
dispatch's llm_config. Does NOT run the agentic LLM loop — the model is
producing audio + text in real time; tool calls come back via the adapter
which is wired into the existing session_store / audio_lifecycle.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.infra.artifacts.convert_tools_to_openai_format import sanitize_tool_name
from app.infra.generation.emit import emit_modality_event
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult
from app.infra.websocket.attempt_types import AttemptAudioReadyData
from app.infra.websocket.generation_types import GenerateErrorApiRequest
from app.infra.websocket.session_store import get_session_by_group_id
from app.infra.websocket.socket_event import EmitFn, internal_event
from app.infra.websocket.tool_call_utils import build_tool_output_schemas


async def execute_audio_dispatch(
    *,
    dispatch: AgentDispatch,
    prepared: PrepareGenerationResult,
    sid: str,
    emit: EmitFn,
) -> None:
    """Open a realtime audio session for this dispatch.

    On success emits ``attempt.generate.audio.session_start``; the live
    session then produces ``attempt.generate.audio.*`` events for the
    duration of the call. On failure emits ``attempt.generate.audio.error``
    and removes the session.
    """
    from app.infra.websocket.audio_lifecycle import get_audio_adapter
    from app.infra.websocket.session_store import (
        create_session,
        get_session_by_conversation_id,
        remove_session,
    )

    llm_config = dispatch.llm_config
    api_key = llm_config.get("api_key")
    artifact_type = prepared.artifact_type
    group_id = str(prepared.group_id)
    run_id = str(prepared.run_id)
    session_id = str(prepared.session_id)
    resource_type = dispatch.resource_types[0] if dispatch.resource_types else artifact_type

    if not api_key:
        await emit_modality_event(
            emit,
            "audio",
            "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message="No API key configured for voice mode",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
            artifact_type=artifact_type,
        )
        return

    metadata = dispatch.metadata or {}
    chat_id = dispatch.chat_id or metadata.get("chat_id") or group_id
    conversation_id = dispatch.conversation_id or metadata.get("conversation_id")
    voice = llm_config.get("voice") or "alloy"

    # Session reuse: if a live realtime session already exists for this
    # conversation, treat this generate as the next turn — rebind per-turn
    # state and skip creating a fresh session. The adapter's own guard in
    # initialize_session will no-op the WS open when it finds the existing
    # connection on this same session object.
    existing = (
        get_session_by_conversation_id(str(conversation_id))
        if conversation_id
        else None
    )
    if existing is not None:
        session = existing
        # Most session scalars stay pinned to the original values (sid,
        # session_id, etc.). Update the handles that reflect THIS turn.
        session.run_id = run_id
        session.group_id = group_id
        session.artifact_type = artifact_type
        session.resource_type = resource_type
        if metadata:
            session.metadata.update(metadata)
    else:
        session = create_session(
            sid=sid,
            chat_id=str(chat_id),
            run_id=run_id,
            group_id=group_id,
            conversation_id=conversation_id,
            session_id=session_id,
            profile_id=str(prepared.profile_id),
            artifact_type=artifact_type,
            resource_type=resource_type,
            metadata=metadata,
        )

    # Reset per-turn assistant audio accumulator — the realtime adapter
    # fills this as the model speaks, then flushes to disk via
    # audio_upload_attempt_impl on response.audio.done and emits an
    # attempt.chat.assistant_audio event carrying the resulting audios_id.
    session.assistant_audio_buffer = bytearray()

    # Surface tool output-field schemas so the adapter can resolve streamed
    # tool-call arguments into resource fields during the session.
    session.tool_output_schemas = build_tool_output_schemas(dispatch.tools or [])

    # Index the full tool defs by sanitized name so the realtime downlink
    # loop can execute function calls and feed results back to the provider.
    tool_def_by_name: dict[str, dict[str, Any]] = {}
    for tool_def in dispatch.tools or []:
        if isinstance(tool_def, dict) and tool_def.get("name"):
            tool_def_by_name[sanitize_tool_name(tool_def["name"])] = tool_def
    session.tool_def_by_name = tool_def_by_name

    adapter = get_audio_adapter()

    # Stitch the system + developer messages the prepare step produced
    # into a single ``instructions`` string for session.update. The
    # attempt-realtime agent's prompt (seeded in
    # database/seeds/prompts/attempt-realtime.{system,instructions}.jinja)
    # enforces the verbatim rule: speak and record the same text per turn.
    instructions_parts: list[str] = []
    for msg in dispatch.messages or []:
        if isinstance(msg, dict) and msg.get("role") in ("system", "developer"):
            content = msg.get("content") or ""
            if isinstance(content, str) and content.strip():
                instructions_parts.append(content)
    session_instructions = "\n\n".join(instructions_parts) or None

    try:
        await adapter.initialize_session(
            session=session,
            api_key=api_key,
            base_url=llm_config.get("base_url"),
            model=llm_config.get("model"),
            voice=voice,
            instructions=session_instructions,
            tools=list(dispatch.tools or []),
        )
    except Exception as exc:
        remove_session(group_id)
        await emit_modality_event(
            emit,
            "audio",
            "error",
            GenerateErrorApiRequest(
                sid=sid,
                error_message=f"Failed to connect to voice service: {exc}",
                artifact_type=artifact_type,
                group_id=group_id,
            ).model_dump(),
            artifact_type=artifact_type,
        )
        return

    # Emit the canonical session-start event (kept for log filter +
    # observability), then directly translate to the client-facing
    # voice_ready signal that arms the mic. Previously the rename
    # lived in ws/output/.../audio_session_start.py — moved here so
    # the workflow is readable top-to-bottom at the emit site.
    session = get_session_by_group_id(group_id)
    chat_id = session.chat_id if session else group_id
    await emit(
        [
            internal_event(
                "attempt.generate.audio.session_start",
                {
                    "sid": sid,
                    "group_id": group_id,
                    "run_id": run_id,
                    "session_id": session_id,
                    "artifact_type": artifact_type,
                    "type": "start",
                    "message": "Audio session ready",
                    "metadata": metadata or None,
                },
            ),
            internal_event(
                "attempt.chat.voice_ready",
                AttemptAudioReadyData(
                    sid=sid,
                    chat_id=chat_id,
                    success=True,
                    message="Voice session ready",
                ).model_dump(mode="json"),
            ),
        ]
    )


__all__ = ["execute_audio_dispatch"]


# Silence unused-import warnings for uuid/sanitize_tool_name if future helpers need them.
_ = (uuid, sanitize_tool_name, Any)
