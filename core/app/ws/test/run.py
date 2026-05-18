"""Input: test.run — canonical WS handler.

Mirrors ws/attempt/start.py. Runs ``test_run_internal_impl`` directly
through the audit framework. The test.run.triggered internal event used by
non-canonical surfaces still flows because the impl emits it itself.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.client_types import TestRunPayload
from app.infra.test.run import TestRunInternalResult, test_run_internal_impl


@sio.on("test.run")  # type: ignore
async def test_run(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = TestRunPayload(**data)
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
        artifact="test", operation="run",
        profile_id=identity.profile_id, session_id=identity.session_id,
        sid=sid,
        runner=lambda: test_run_internal_impl(runner_data, audit=False),
        arguments=payload.model_dump(mode="json"),
        response_model=TestRunInternalResult,
    )
