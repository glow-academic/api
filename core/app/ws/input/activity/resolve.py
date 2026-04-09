"""Input: activity.resolve — resolve a problem entry."""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@sio.event  # type: ignore
async def activity_resolve(sid: str, data: dict[str, Any]) -> None:
    try:
        profile_id_str = await find_profile_by_socket(sid)
        if not profile_id_str:
            await sio.emit(
                "activity.resolve.failed",
                {"message": "Profile not found. Please reconnect."},
                room=sid,
            )
            return

        session_id_str = await find_session_by_socket(sid)
        if not session_id_str:
            await sio.emit(
                "activity.resolve.failed",
                {"message": "Session not found. Please reconnect."},
                room=sid,
            )
            return

        await internal_sio.emit(
            "activity.resolve",
            {
                "sid": sid,
                "profile_id": profile_id_str,
                "session_id": session_id_str,
                "problem_id": data.get("problem_id"),
                "resolved": data.get("resolved", True),
            },
        )
    except Exception as e:
        logger.exception(f"Error in activity.resolve input: {e}")
        await sio.emit(
            "activity.resolve.failed",
            {"message": f"Invalid request: {e}"},
            room=sid,
        )
