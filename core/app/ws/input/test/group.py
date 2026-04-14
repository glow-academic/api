"""Input: test.group (time-windowed artifact grouping) + test_group (orchestration).

test.group — resolve or create a time-windowed group for the test artifact.
test_group — run all runs in a group sequentially (orchestration pipeline).
"""

from typing import Any
from uuid import UUID

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.client_types import TestGroupPayload
from app.infra.test.group import (
    GroupTestApiRequest,
    group_test_impl,
)
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.test_types import TestErrorData
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


# ---------------------------------------------------------------------------
# Time-windowed artifact grouping (test.group)
# ---------------------------------------------------------------------------


@sio.on("test.group")  # type: ignore
async def test_group_artifact(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GroupTestApiRequest(**data)
    except Exception:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="test",
        operation="group",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: group_test_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# Orchestration pipeline (test_group — sequential runs)
# ---------------------------------------------------------------------------


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
