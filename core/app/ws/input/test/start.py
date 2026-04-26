"""Input: test.start — canonical WS handler.

Mirrors ws/input/attempt/start.py. Runs ``test_start_internal_impl`` directly
through the audit framework so ``test.start.completed`` (with ``test_id`` and
``benchmark_id``) flows back to the client over Socket.IO.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.client_types import TestStartPayload
from app.infra.test.start import TestStartInternalResult, test_start_internal_impl
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


@sio.on("test.start")  # type: ignore
async def test_start(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        logger.warning("test.start dropped — no socket identity for sid %s", sid)
        return

    try:
        payload = TestStartPayload(**data)
    except Exception as e:
        logger.warning("test.start payload validation failed for sid %s: %s", sid, e)
        return

    logger.info("test.start handling sid=%s eval_id=%s", sid, payload.eval_id)

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
        artifact="test", operation="start",
        profile_id=identity.profile_id, session_id=identity.session_id,
        sid=sid, rooms=[sid],
        runner=lambda: test_start_internal_impl(runner_data, audit=False),
        arguments=payload.model_dump(mode="json"),
        response_model=TestStartInternalResult,
    )
