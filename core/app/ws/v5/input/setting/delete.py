"""Input: setting.delete"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.setting.delete import delete_setting_impl
from app.infra.setting.types import DeleteSettingApiRequest

internal_sio = get_internal_sio()


@sio.on("setting.delete")  # type: ignore
async def setting_delete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DeleteSettingApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("setting.delete.failed", {
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
        operation="delete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: delete_setting_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            setting_ids=payload.setting_ids,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
