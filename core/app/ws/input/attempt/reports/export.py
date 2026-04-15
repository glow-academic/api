"""Input: reports.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.reports.export import export_reports_impl
from app.infra.reports.group import group_reports_impl


@sio.on("attempt.reports.export")  # type: ignore
async def reports_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    session_id = identity.session_id
    if session_id:
        group_result = await group_reports_impl(
            pool, redis, profile_id=identity.profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="reports",
        operation="export",
        profile_id=identity.profile_id,
        session_id=session_id,
        group_id=group_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_reports_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
        ),
        arguments=data or {},
    )
