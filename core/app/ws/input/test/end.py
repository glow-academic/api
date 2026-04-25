"""Input: test.end — canonical WS handler.

Mirrors ws/input/attempt/start.py. Runs ``test_end_internal_impl`` directly
through the audit framework.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.client_types import TestEndPayload
from app.infra.test.end import TestEndInternalResult, test_end_internal_impl


@sio.on("test.end")  # type: ignore
async def test_end(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = TestEndPayload(**data)
    except Exception:
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
        artifact="test", operation="end",
        profile_id=identity.profile_id, session_id=identity.session_id,
        sid=sid, rooms=[sid],
        runner=lambda: test_end_internal_impl(runner_data, audit=False),
        arguments=payload.model_dump(mode="json"),
        response_model=TestEndInternalResult,
    )
