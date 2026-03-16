"""Input: activity.refresh"""

from typing import Any

from app.infra.activity.refresh import refresh_activity_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("activity.refresh")  # type: ignore
async def activity_refresh(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="activity",
        operation="refresh",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: refresh_activity_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
        ),
        arguments={},
    )
