"""Output: invocation.decrypt — decrypt an invocation key."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.decrypt import resolve_decrypt
from app.infra.tools.entries.append_call_event import append_call_event
from app.tools.entries.invocation.get import get_invocations
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("invocation.decrypt")  # type: ignore
async def invocation_decrypt_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "invocation.decrypt", data, UPLOAD_FOLDER)

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        await sio.emit("invocation.decrypt.failed", {"message": "Missing profile_id"}, room=sid)
        return

    try:
        pool = get_pool()
        redis = get_redis_client()
        profile_id = UUID(profile_id_str)
        invocation_id = UUID(data["invocation_id"])
        key_id = UUID(data["key_id"])
        bypass_cache = data.get("bypass_cache", False)

        # Validate key belongs to this invocation
        async with pool.acquire() as conn:
            invocations = await get_invocations(conn, [invocation_id])

        if not invocations:
            await sio.emit("invocation.decrypt.failed", {"message": "Invocation not found"}, room=sid)
            return

        invocation = invocations[0]
        if key_id not in (invocation.key_ids or []):
            await sio.emit("invocation.decrypt.failed", {"message": "Key does not belong to this invocation"}, room=sid)
            return

        result = await resolve_decrypt(
            pool, redis, profile_id=profile_id, key_id=key_id, bypass_cache=bypass_cache,
        )

        await sio.emit(
            "invocation.decrypt.completed",
            {"key": result.key, "name": result.name, "actor_name": result.actor_name},
            room=sid,
        )

    except Exception as e:
        logger.exception(f"Error in invocation.decrypt output: {e}")
        await sio.emit("invocation.decrypt.failed", {"message": f"Failed to decrypt: {e}"}, room=sid)
