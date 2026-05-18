"""Input: invocation.drafts"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.invocation.drafts import list_invocation_drafts_impl


@sio.on("test.invocation_drafts")  # type: ignore
async def invocation_drafts(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="test",
        operation="invocation_drafts",
        profile_id=identity.profile_id,
        sid=sid,
        runner=lambda: list_invocation_drafts_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
        ),
        arguments={},
    )
