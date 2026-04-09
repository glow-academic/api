"""Output: emulate — create emulation grant."""

from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.emulate import resolve_emulation
from app.infra.identity.socket import resolve_socket_identity
from app.infra.tools.entries.append_call_event import append_call_event
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("emulate")  # type: ignore
async def emulate_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "emulate", data, UPLOAD_FOLDER)

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        await sio.emit("emulate_error", {"message": "Missing profile_id"}, room=sid)
        return

    try:
        profile_id = UUID(profile_id_str)
        target_profile_id = UUID(data["target_profile_id"])
        bypass_cache = data.get("bypass_cache", False)
        pool = get_pool()
        redis = get_redis_client()

        # Resolve actor_profile_id from socket identity
        identity = await resolve_socket_identity(sid)
        actor_profile_id = identity.actor_profile_id if identity else None

        result = await resolve_emulation(
            pool,
            redis,
            requester_profile_id=profile_id,
            target_profile_id=target_profile_id,
            ttl_minutes=data.get("ttl_minutes") or 120,
            bypass_cache=bypass_cache,
            actor_profile_id=actor_profile_id,
        )

        if not result.allowed:
            await sio.emit(
                "emulate_error",
                {"message": result.reason or "Forbidden"},
                room=sid,
            )
            return

        await invalidate_tags(["profile"], redis=redis)

        await sio.emit(
            "emulate_result",
            {
                "allowed": result.allowed,
                "reason": result.reason,
                "grant_id": str(result.grant_id) if result.grant_id else None,
                "expires_at": result.expires_at.isoformat() if result.expires_at else None,
            },
            room=sid,
        )

    except Exception as e:
        logger.exception(f"Error in emulate output: {e}")
        await sio.emit(
            "emulate_error", {"message": f"Failed to emulate: {e}"}, room=sid
        )
