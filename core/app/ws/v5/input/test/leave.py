"""Input: test_leave — leave a test room."""

from typing import Any

from app.infra.globals import sio
from app.infra.test.client_types import TestLeavePayload
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


@sio.event  # type: ignore
async def test_leave(sid: str, data: dict[str, Any]) -> None:
    try:
        payload = TestLeavePayload(**data)
        room_name = f"test_{payload.invocation_id}"
        await sio.leave_room(sid, room_name)
    except Exception as e:
        logger.exception(f"Error in test_leave: {e}")
