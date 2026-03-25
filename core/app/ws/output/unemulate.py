"""Output: unemulate — exit innermost emulation layer."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.emulate import resolve_unemulation
from app.infra.identity.socket import resolve_socket_identity
from app.infra.tools.entries.append_call_event import append_call_event
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("unemulate")  # type: ignore
async def unemulate_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "unemulate", data, UPLOAD_FOLDER)

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        await sio.emit(
            "unemulate_error", {"message": "Missing profile_id"}, room=sid
        )
        return

    try:
        pool = get_pool()
        redis = get_redis_client()

        # Resolve actor_profile_id from socket identity
        identity = await resolve_socket_identity(sid)
        actor_profile_id = identity.actor_profile_id if identity else None
        origin = actor_profile_id or UUID(profile_id_str)

        result = await resolve_unemulation(pool, actor_profile_id=origin)

        if not result.ok:
            await sio.emit(
                "unemulate_error",
                {"message": result.reason or "Cannot exit emulation"},
                room=sid,
            )
            return

        await invalidate_tags(["profile"], redis=redis)

        await sio.emit(
            "unemulate_result",
            {"ok": result.ok, "reason": result.reason},
            room=sid,
        )

    except Exception as e:
        logger.exception(f"Error in unemulate output: {e}")
        await sio.emit(
            "unemulate_error", {"message": f"Failed to unemulate: {e}"}, room=sid
        )
