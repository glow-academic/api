"""Input: test_join — join a test room for real-time updates."""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.test.client_types import TestJoinPayload
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@sio.event  # type: ignore
async def test_join(sid: str, data: dict[str, Any]) -> None:
    try:
        payload = TestJoinPayload(**data)
        profile_id_str = await find_profile_by_socket(sid)
        if not profile_id_str:
            await internal_sio.emit(
                "test_error",
                {"sid": sid, "rooms": [sid], "invocation_id": str(payload.invocation_id), "message": "Profile not found. Please reconnect.", "error_type": "join"},
            )
            return

        invocation_id_str = str(payload.invocation_id)
        room_name = f"test_{invocation_id_str}"
        await sio.enter_room(sid, room_name)

        await internal_sio.emit(
            "test_joined",
            {"sid": sid, "rooms": [sid, room_name], "invocation_id": invocation_id_str, "success": True},
        )
    except Exception as e:
        logger.exception(f"Error in test_join: {e}")
        await internal_sio.emit(
            "test_error",
            {"sid": sid, "rooms": [sid], "invocation_id": str(data.get("invocation_id", "")), "message": f"Failed to join room: {e}", "error_type": "join"},
        )
