"""Input: field.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.field.export import export_field_impl
from app.infra.field.types import ExportFieldApiRequest
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("field.export")  # type: ignore
async def field_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportFieldApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("field.export.failed", {
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
        artifact="field",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_field_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            field_id=payload.field_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
