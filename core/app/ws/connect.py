"""Input: connect — WebSocket connection with token-based auth.

Multiple sockets per profile are allowed. The first socket for a profile
triggers the activity-create row; subsequent sockets just join the room.
This makes multi-tab, multi-device, and the debug-panel-as-client all
work without anyone kicking anyone else off.
"""

import uuid

from app.infra.globals import get_pool, sio
from app.infra.identity.socket import store_socket_identity
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
            from app.infra.identity.resolve_identity import (
                extract_bearer_token,
                resolve_identity,
            )

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

    # Multi-socket: add this sid to the profile's set. The helper returns
    # True iff this is the first socket for the profile — only then do
    # we record an activity row, since nothing observable about presence
    # changes when a 2nd/3rd socket joins.
    is_first = await set_socket_owner(profile_id, sid)
    await sio.enter_room(sid, profile_id)

    if session_id:
        await _store_session_id(sid, session_id)

    if is_first:
        await _mark_profile_active(profile_id, session_id)

    return True
