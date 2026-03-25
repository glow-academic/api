"""Input: profile.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.profile.export import export_profile_impl
from app.infra.profile.types import ExportProfileApiRequest

internal_sio = get_internal_sio()


@sio.on("profile.export")  # type: ignore
async def profile_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportProfileApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("profile.export.failed", {
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
        artifact="profile",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_profile_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            profile_export_id=payload.profile_export_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
