"""Input: disconnect — WebSocket disconnection with cleanup."""

from app.infra.globals import get_internal_sio, sio
from app.infra.identity.socket import remove_socket_identity
from app.infra.websocket.decrement_guest_count import decrement_guest_count
from app.infra.websocket.find_chats_by_socket import find_chats_by_socket
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.is_guest_socket import is_guest_socket
from app.infra.websocket.remove_active_connection import remove_active_connection
from app.infra.websocket.remove_guest_socket import remove_guest_socket
from app.infra.websocket.remove_socket_owner import remove_socket_owner
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def _mark_profile_inactive(profile_id: str, sid: str) -> None:
    import uuid

    try:
        session_id_str = await find_session_by_socket(sid)
        if not session_id_str:
            return
        from app.infra.globals import get_pool
        from app.tools.entries.activity.create import create_activity

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
async def disconnect(sid: str) -> None:
    """Handle WebSocket disconnection with cleanup."""
    profile_to_cleanup = await find_profile_by_socket(sid)
    if profile_to_cleanup:
        await remove_socket_owner(profile_to_cleanup)
        await _mark_profile_inactive(profile_to_cleanup, sid)
    await remove_socket_identity(sid)

    if await is_guest_socket(sid):
        try:
            await remove_guest_socket(sid)
            await decrement_guest_count()
        except Exception:
            logger.warning("Failed to clean up guest socket %s", sid)

    try:
        from app.infra.websocket.audio_lifecycle import cleanup_audio_session
        from app.infra.websocket.session_store import get_session_by_sid

        voice_session = get_session_by_sid(sid)
        if voice_session:
            await cleanup_audio_session(voice_session)
    except Exception:
        logger.warning("Failed to clean up voice session for socket %s", sid)

    chat_ids = await find_chats_by_socket(sid)
    for chat_id in chat_ids:
        await remove_active_connection(chat_id, sid)

    internal_sio = get_internal_sio()
    await internal_sio.emit(
        "disconnected",
        {
            "sid": sid,
            "rooms": [profile_to_cleanup] if profile_to_cleanup else [],
            "profile_id": profile_to_cleanup or "",
        },
    )
