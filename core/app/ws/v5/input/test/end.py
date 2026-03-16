"""Input: test_end — end a single invocation, optionally grade."""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.test.client_types import TestEndPayload
from app.infra.websocket.test_types import TestErrorData
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@sio.event  # type: ignore
async def test_end(sid: str, data: dict[str, Any]) -> None:
    try:
        payload = TestEndPayload(**data)
        profile_id_str = await find_profile_by_socket(sid)
        if not profile_id_str:
            await internal_sio.emit(
                "test_error",
                TestErrorData(sid=sid, message="Profile not found. Please reconnect.", error_type="auth").model_dump(mode="json"),
            )
            return

        session_id_str = await find_session_by_socket(sid)
        if not session_id_str:
            await internal_sio.emit(
                "test_error",
                TestErrorData(sid=sid, message="Session not found. Please reconnect.", error_type="auth").model_dump(mode="json"),
            )
            return

        await internal_sio.emit(
            "test_end",
            {"sid": sid, "profile_id": profile_id_str, "session_id": session_id_str, **payload.model_dump(mode="json")},
        )
    except Exception as e:
        logger.exception(f"Error in test_end: {e}")
        await internal_sio.emit(
            "test_error",
            TestErrorData(sid=sid, message=f"Failed to end invocation: {e}", error_type="end").model_dump(mode="json"),
        )
