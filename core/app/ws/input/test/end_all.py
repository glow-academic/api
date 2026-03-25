"""Input: test_end_all — end all remaining invocations.

Delegates to test_proceed(complete_all=True).
"""

from typing import Any

from app.infra.globals import get_internal_sio, sio
from app.infra.test.client_types import TestEndAllPayload
from app.infra.websocket.test_types import TestErrorData, TestProceedData
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@sio.event  # type: ignore
async def test_end_all(sid: str, data: dict[str, Any]) -> None:
    try:
        payload = TestEndAllPayload(**data)
        await internal_sio.emit(
            "test_proceed",
            TestProceedData(sid=sid, test_id=str(payload.test_id), complete_all=True).model_dump(mode="json"),
        )
    except Exception as e:
        logger.exception(f"Error in test_end_all: {e}")
        await internal_sio.emit(
            "test_error",
            TestErrorData(sid=sid, message=f"Failed to end all invocations: {e}", error_type="end").model_dump(mode="json"),
        )
