"""Input: session.get"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.session.get import get_session_detail_impl

internal_sio = get_internal_sio()


class SessionGetPayload(BaseModel):
    """Payload for session.get socket event."""

    session_id: UUID = Field(...)


@sio.on("session.get")  # type: ignore
async def session_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = SessionGetPayload(**data)
    except Exception as e:
        await internal_sio.emit("session.get.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="session",
        operation="get",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_session_detail_impl(
            pool,
            profile_id=identity.profile_id,
            session_id=payload.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
