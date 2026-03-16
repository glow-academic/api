"""Input: setting.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.setting.export import export_setting_impl
from app.infra.setting.types import ExportSettingApiRequest

internal_sio = get_internal_sio()


@sio.on("setting.export")  # type: ignore
async def setting_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportSettingApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("setting.export.failed", {
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
        artifact="setting",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_setting_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            setting_id=payload.setting_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
