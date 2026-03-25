"""Input: parameter.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.parameter.export import export_parameter_impl
from app.infra.parameter.types import ExportParameterApiRequest

internal_sio = get_internal_sio()


@sio.on("parameter.export")  # type: ignore
async def parameter_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportParameterApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("parameter.export.failed", {
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
        artifact="parameter",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_parameter_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            parameter_id=payload.parameter_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
