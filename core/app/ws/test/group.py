"""Input: test.group — time-windowed artifact grouping for the test artifact.

The legacy ``test_group`` orchestration entry point was removed: nobody
emitted that event from anywhere in the codebase, and the orchestration
chain is now driven directly from ``test_next_impl`` calling
``test_group_impl`` inline. The WS audit-wrapped ``test.group`` handler
below is the canonical group-resolution path used by clients.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.group import (
    GroupTestApiRequest,
    group_test_impl,
)


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
        runner=lambda: group_test_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
