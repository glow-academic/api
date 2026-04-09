"""Output: setting.decrypt — decrypt a setting key."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.decrypt import resolve_decrypt
from app.infra.tools.entries.append_call_event import append_call_event
from app.tools.artifacts.setting.get import get_settings
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("setting.decrypt")  # type: ignore
async def setting_decrypt_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "setting.decrypt", data, UPLOAD_FOLDER)

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        await sio.emit("setting.decrypt.failed", {"message": "Missing profile_id"}, room=sid)
        return

    try:
        pool = get_pool()
        redis = get_redis_client()
        profile_id = UUID(profile_id_str)
        setting_id = UUID(data["setting_id"])
        key_id = UUID(data["key_id"])
        bypass_cache = data.get("bypass_cache", False)

        # Validate key belongs to this setting
        async with pool.acquire() as conn:
            settings = await get_settings(
                conn, [setting_id], provider_keys=True, auth_item_keys=True, active=None,
            )

        if not settings:
            await sio.emit("setting.decrypt.failed", {"message": "Setting not found"}, room=sid)
            return

        setting = settings[0]
        all_key_ids = list(setting.provider_key_ids or []) + list(setting.auth_item_keys_ids or [])
        if key_id not in all_key_ids:
            await sio.emit("setting.decrypt.failed", {"message": "Key does not belong to this setting"}, room=sid)
            return

        result = await resolve_decrypt(
            pool, redis, profile_id=profile_id, key_id=key_id, bypass_cache=bypass_cache,
        )

        await sio.emit(
            "setting.decrypt.completed",
            {"key": result.key, "name": result.name, "actor_name": result.actor_name},
            room=sid,
        )

    except Exception as e:
        logger.exception(f"Error in setting.decrypt output: {e}")
        await sio.emit("setting.decrypt.failed", {"message": f"Failed to decrypt: {e}"}, room=sid)
