"""Input: leaderboard.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.leaderboard.export import export_leaderboard_impl


@sio.on("leaderboard.export")  # type: ignore
async def leaderboard_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="leaderboard",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_leaderboard_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
        ),
        arguments=data or {},
    )
