"""Input: connect — WebSocket connection with token-based auth."""

import uuid

from app.infra.globals import get_internal_sio, get_pool, sio
from app.infra.identity.socket import store_socket_identity
from app.infra.websocket.remove_socket_owner import remove_socket_owner
from app.infra.websocket.get_socket_owner import get_socket_owner
from app.infra.websocket.set_socket_owner import set_socket_owner
from app.tools.entries.activity.create import create_activity
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def _store_session_id(sid: str, session_id: str) -> None:
    try:
        from app.infra.globals import get_redis_client

        redis_client = get_redis_client()
        if redis_client:
            await redis_client.setex(f"socket_session:{sid}", 86400, session_id)
    except Exception:
        logger.warning("Failed to store session_id in Redis for sid %s", sid)


async def _mark_profile_active(profile_id: str, session_id: str | None) -> None:
    if not session_id:
        return
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            await create_activity(
                conn,
                session_id=uuid.UUID(session_id),
                profile_id=uuid.UUID(profile_id),
            )
    except Exception:
        logger.warning("Failed to mark profile %s active", profile_id)


async def _mark_profile_inactive(profile_id: str, sid: str) -> None:
    try:
        from app.infra.websocket.find_session_by_socket import find_session_by_socket

        session_id_str = await find_session_by_socket(sid)
        if not session_id_str:
            return
        pool = get_pool()
        async with pool.acquire() as conn:
            await create_activity(
                conn,
                session_id=uuid.UUID(session_id_str),
                profile_id=uuid.UUID(profile_id),
            )
    except Exception:
        logger.warning("Failed to mark profile %s inactive", profile_id)


@sio.event  # type: ignore
async def connect(
    sid: str,
    environ: dict[str, str],
    auth: dict[str, str] | None,
) -> bool:
    """Handle WebSocket connection with token-based auth."""
    identity = None

    if auth and auth.get("token"):
        try:
            from app.infra.identity.license_key import validate_license_key
            from app.infra.identity.resolve_identity import (
                extract_bearer_token,
                resolve_identity,
            )

            api_key = auth.get("apiKey")
            if api_key:
                license_info = await validate_license_key(api_key)
                if not license_info.valid:
                    return False

            token = extract_bearer_token(auth["token"])
            if token:
                pool = get_pool()
                identity = await resolve_identity(token, pool)
        except Exception:
            logger.warning("Failed to resolve identity from auth token for sid %s", sid)

    if not identity:
        logger.warning("Rejected unauthenticated socket connection for sid %s", sid)
        return False

    profile_id = str(identity.profile_id)
    session_id = str(identity.session_id)

    await store_socket_identity(sid, identity)

    old_sid = await get_socket_owner(profile_id)
    if old_sid and old_sid != sid:
        await remove_socket_owner(profile_id)
        await _mark_profile_inactive(profile_id, old_sid)
        await sio.disconnect(old_sid)

    await set_socket_owner(profile_id, sid)
    await sio.enter_room(sid, profile_id)

    if session_id:
        await _store_session_id(sid, session_id)

    await _mark_profile_active(profile_id, session_id)

    internal_sio = get_internal_sio()
    await internal_sio.emit(
        "connected",
        {
            "sid": sid,
            "rooms": [profile_id],
            "profile_id": profile_id,
            "session_id": session_id,
        },
    )

    return True
