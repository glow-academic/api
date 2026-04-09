"""Input: setting.decrypt"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.setting.decrypt import decrypt_setting_impl
from app.infra.setting.types import DecryptSettingKeyApiRequest

internal_sio = get_internal_sio()


@sio.on("setting.decrypt")  # type: ignore
async def setting_decrypt(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DecryptSettingKeyApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("setting.decrypt.failed", {
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
        operation="decrypt",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: decrypt_setting_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            setting_id=payload.setting_id,
            key_id=payload.key_id,
            bypass_cache=data.get("bypass_cache", False),
        ),
        arguments=payload.model_dump(mode="json"),
    )
