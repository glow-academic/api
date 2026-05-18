"""Input: practice.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.routes.attempt.practice import get_practice_internal


@sio.on("attempt.practice")  # type: ignore
async def practice_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="practice_get",
        profile_id=identity.profile_id,
        sid=sid,
        runner=lambda: get_practice_internal(
            pool,
            profile_id=identity.profile_id,
        ),
        arguments=data or {},
    )
