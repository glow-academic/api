"""Input: generate — unified generation entry point."""

from __future__ import annotations

import uuid
from typing import Any

from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.typed_emit import emit_to_internal
from app.infra.websocket.generation_types import GenerateErrorApiRequest, GeneratePayload
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


async def _emit_error(sid: str, message: str, artifact_type: str) -> None:
    await emit_to_internal(
        "generate_call_error",
        GenerateErrorApiRequest(
            sid=sid,
            error_message=message,
            artifact_type=artifact_type,
            resource_type=artifact_type,
        ),
        sid=sid,
    )


@sio.event  # type: ignore
async def generate(sid: str, data: dict[str, Any]) -> None:
    """Handle unified generate event.

    Resolves identity context from sid at the client boundary,
    then emits to internal bus for the generation pipeline.
    """
    artifact_types_raw = data.get("artifact_types") or []
    artifact_type = (
        artifact_types_raw[0]["name"]
        if artifact_types_raw and isinstance(artifact_types_raw[0], dict)
        else "unknown"
    )
    try:
        payload = GeneratePayload(**data)

        profile_id_str = await find_profile_by_socket(sid)
        if not profile_id_str:
            await _emit_error(
                sid, "Profile not found. Please reconnect.", artifact_type
            )
            return

        session_id_str = await find_session_by_socket(sid)
        if not session_id_str:
            await _emit_error(
                sid, "Session not found. Please reconnect.", artifact_type
            )
            return

        profile_id = uuid.UUID(profile_id_str)
        session_id = uuid.UUID(session_id_str)
        redis = get_redis_client()
        pool = get_pool()
        profile_ctx = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id
        )

        if not profile_ctx:
            await _emit_error(
                sid, "Profile context not found. Please reconnect.", artifact_type
            )
            return

        group_id = data.get("group_id")
        if not group_id:
            await _emit_error(sid, "group_id is required.", artifact_type)
            return

        await internal_sio.emit(
            "generate",
            {
                "sid": sid,
                "profile_id": profile_id_str,
                "profiles_id": str(profile_ctx.profiles_id),
                "session_id": session_id_str,
                "group_id": group_id,
                "requests_per_day": profile_ctx.requests_per_day,
                **payload.model_dump(mode="json"),
            },
        )
    except Exception as e:
        await _emit_error(sid, f"Invalid request: {str(e)}", artifact_type)
