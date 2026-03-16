"""Input: problem — create a problem/bug report entry."""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@sio.event  # type: ignore
async def problem(sid: str, data: dict[str, Any]) -> None:
    try:
        profile_id_str = await find_profile_by_socket(sid)
        if not profile_id_str:
            await sio.emit(
                "problem_error",
                {"message": "Profile not found. Please reconnect."},
                room=sid,
            )
            return

        session_id_str = await find_session_by_socket(sid)
        if not session_id_str:
            await sio.emit(
                "problem_error",
                {"message": "Session not found. Please reconnect."},
                room=sid,
            )
            return

        problem_type = data.get("type")
        message = data.get("message")

        if not problem_type or problem_type not in ("feature", "bug", "question", "other"):
            await sio.emit(
                "problem_error",
                {"message": f"Invalid problem type: {problem_type}"},
                room=sid,
            )
            return

        if not message or not message.strip():
            await sio.emit(
                "problem_error",
                {"message": "Message is required."},
                room=sid,
            )
            return

        if len(message) > 1000:
            await sio.emit(
                "problem_error",
                {"message": "Message must be less than 1000 characters."},
                room=sid,
            )
            return

        await internal_sio.emit(
            "problem",
            {
                "sid": sid,
                "profile_id": profile_id_str,
                "session_id": session_id_str,
                "type": problem_type,
                "message": message,
            },
        )
    except Exception as e:
        logger.exception(f"Error in problem input: {e}")
        await sio.emit(
            "problem_error",
            {"message": f"Invalid request: {e}"},
            room=sid,
        )
