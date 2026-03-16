"""Input: auth.export"""

from typing import Any

from app.infra.auth.export import export_auth_impl
from app.infra.auth.types import ExportAuthApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("auth.export")  # type: ignore
async def auth_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportAuthApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("auth.export.failed", {
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
        artifact="auth",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_auth_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            auth_id=payload.auth_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
