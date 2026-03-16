"""Input: context — profile identity + permissions + theme."""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@sio.event  # type: ignore
async def context(sid: str, data: dict[str, Any]) -> None:
    try:
        profile_id_str = await find_profile_by_socket(sid)
        if not profile_id_str:
            await sio.emit(
                "context_error",
                {"message": "Profile not found. Please reconnect."},
                room=sid,
            )
            return

        session_id_str = await find_session_by_socket(sid)

        await internal_sio.emit(
            "context",
            {
                "sid": sid,
                "profile_id": profile_id_str,
                "session_id": session_id_str,
                "bypass_cache": data.get("bypass_cache", False),
            },
        )
    except Exception as e:
        logger.exception(f"Error in context input: {e}")
        await sio.emit(
            "context_error",
            {"message": f"Invalid request: {e}"},
            room=sid,
        )
