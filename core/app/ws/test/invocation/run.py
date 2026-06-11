"""Input: test.invocation_run — canonical WS handler.

Mirrors the HTTP ``POST /test/invocation_run`` route (and ws/test/run.py,
which serves the ``test.run`` alias): binds a runs_entry to a test
invocation through the audit framework so ``test.invocation_run.completed``
(the event the client's WS command channel awaits) flows back over
Socket.IO. Without this handler the client-emitted ``test.invocation_run``
event had no ``sio.on`` listener and the client hung for the full 30s
command timeout.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.client_types import TestRunPayload
from app.infra.test.run import TestRunInternalResult, test_run_internal_impl


@sio.on("test.invocation_run")  # type: ignore
async def test_invocation_run(sid: str, data: dict[str, Any]) -> None:
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
        artifact="test", operation="invocation_run",
        profile_id=identity.profile_id, session_id=identity.session_id,
        sid=sid,
        runner=lambda: test_run_internal_impl(runner_data, audit=False),
        arguments=payload.model_dump(mode="json"),
        response_model=TestRunInternalResult,
    )
