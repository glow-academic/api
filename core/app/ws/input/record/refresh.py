"""Input: record.refresh"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.record_refresh import refresh_record_client


@sio.on("record.refresh")  # type: ignore
async def record_refresh(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="record",
        operation="refresh",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: refresh_record_client(
            pool,
            redis,
            profile_id=identity.profile_id,
        ),
        arguments={},
    )
