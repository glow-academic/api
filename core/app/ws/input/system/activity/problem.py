"""Input: activity.problem"""

from typing import Any

from pydantic import BaseModel, Field

from app.infra.activity.problem import problem_activity_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class ActivityProblemPayload(BaseModel):
    """Payload for activity.problem socket event."""

    type: str = Field(...)
    message: str = Field(...)


@sio.event  # type: ignore
async def problem(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ActivityProblemPayload(**data)
    except Exception as e:
        await internal_sio.emit("activity.problem.failed", {
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
        artifact="activity",
        operation="problem",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: problem_activity_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            type=payload.type,
            message=payload.message,
        ),
        arguments=payload.model_dump(mode="json"),
    )
