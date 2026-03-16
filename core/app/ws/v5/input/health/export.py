"""Input: health.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.health.export import export_health_impl
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("health.export")  # type: ignore
async def health_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="health",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_health_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
        ),
        arguments={},
    )
