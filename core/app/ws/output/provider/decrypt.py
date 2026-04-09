"""Output: provider.decrypt — decrypt a provider key."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.decrypt import resolve_decrypt
from app.infra.tools.entries.append_call_event import append_call_event
from app.tools.artifacts.provider.get import get_providers
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("provider.decrypt")  # type: ignore
async def provider_decrypt_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "provider.decrypt", data, UPLOAD_FOLDER)

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        await sio.emit("provider.decrypt.failed", {"message": "Missing profile_id"}, room=sid)
        return

    try:
        pool = get_pool()
        redis = get_redis_client()
        profile_id = UUID(profile_id_str)
        provider_id = UUID(data["provider_id"])
        key_id = UUID(data["key_id"])
        bypass_cache = data.get("bypass_cache", False)

        # Validate key belongs to this provider
        async with pool.acquire() as conn:
            providers = await get_providers(conn, [provider_id], keys=True, active=None)

        if not providers:
            await sio.emit("provider.decrypt.failed", {"message": "Provider not found"}, room=sid)
            return

        provider = providers[0]
        if key_id not in (provider.key_ids or []):
            await sio.emit("provider.decrypt.failed", {"message": "Key does not belong to this provider"}, room=sid)
            return

        result = await resolve_decrypt(
            pool, redis, profile_id=profile_id, key_id=key_id, bypass_cache=bypass_cache,
        )

        await sio.emit(
            "provider.decrypt.completed",
            {"key": result.key, "name": result.name, "actor_name": result.actor_name},
            room=sid,
        )

    except Exception as e:
        logger.exception(f"Error in provider.decrypt output: {e}")
        await sio.emit("provider.decrypt.failed", {"message": f"Failed to decrypt: {e}"}, room=sid)
