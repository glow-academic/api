"""Input: test.trace — canonical trace-creation handler."""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.trace import (
    TestTraceInternalResult,
    TestTracePayload,
    test_trace_internal_impl,
)
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


@sio.on("test.trace")  # type: ignore
async def test_trace(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        logger.warning("test.trace dropped — no socket identity for sid %s", sid)
        return

    try:
        payload = TestTracePayload(**data)
    except Exception as e:
        logger.warning(
            "test.trace payload validation failed for sid %s: %s (data=%s)",
            sid, e, data,
        )
        return

    pool = get_pool()
    redis = get_redis_client()

    runner_data: dict[str, Any] = {
        "sid": sid,
        "profile_id": str(identity.profile_id),
        "session_id": str(identity.session_id),
        **payload.model_dump(mode="json"),
    }

    await run_artifact_operation_with_audit(
        pool, redis,
        artifact="test", operation="trace",
        profile_id=identity.profile_id, session_id=identity.session_id,
        sid=sid, rooms=[sid],
        runner=lambda: test_trace_internal_impl(runner_data, audit=False),
        arguments=payload.model_dump(mode="json"),
        response_model=TestTraceInternalResult,
    )
