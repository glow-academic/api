"""Input: test_group — run all runs in a group sequentially.

Dual-triggered: client sends this, AND test_next/test_proceed emit it internally.
Emits to internal bus so there's one handler path.
"""

from typing import Any
from uuid import UUID

from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.test.client_types import TestGroupPayload
from app.infra.websocket.test_types import TestErrorData
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@sio.event  # type: ignore
async def test_group(sid: str, data: dict[str, Any]) -> None:
    try:
        payload = TestGroupPayload(**data)
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

        identity = await resolve_profile_identity_context(
            get_pool(), UUID(profile_id_str), get_redis_client(),
            session_id=UUID(session_id_str), test_id=payload.test_id,
        )
        group_id = identity.group_id if identity else None
        if group_id is None:
            raise ValueError(f"Group not found for test {payload.test_id}")

        await internal_sio.emit(
            "test_group",
            {"sid": sid, "profile_id": profile_id_str, **payload.model_dump(mode="json"), "group_id": str(group_id)},
        )
    except Exception as e:
        logger.exception(f"Invalid request in test_group: {e}")
        await internal_sio.emit(
            "test_error",
            TestErrorData(sid=sid, message=f"Invalid request: {e}", error_type="group").model_dump(mode="json"),
        )
