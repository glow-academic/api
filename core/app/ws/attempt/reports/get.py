"""Input: reports.get"""

from typing import Any

from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.reports.get import get_reports_impl
from app.infra.reports.types import ReportsRequest

internal_sio = get_internal_sio()


@sio.on("attempt.reports.get")  # type: ignore
async def reports_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ReportsRequest(**data)
    except Exception as e:
        await internal_sio.emit("attempt.reports_get.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    session_id = identity.session_id
    if session_id:
        group_result = await group_attempt_impl(
            pool, redis, profile_id=identity.profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="reports_get",
        profile_id=identity.profile_id,
        session_id=session_id,
        group_id=group_id,
        sid=sid,
        runner=lambda: get_reports_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
