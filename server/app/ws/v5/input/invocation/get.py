"""Input: invocation.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.invocation.get import get_invocation_impl
from app.infra.invocation.types import GetSuiteRequest

internal_sio = get_internal_sio()


@sio.on("invocation.get")  # type: ignore
async def invocation_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetSuiteRequest(**data)
    except Exception as e:
        await internal_sio.emit("invocation.get.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="invocation",
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_invocation_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            test_id=payload.test_id,
            draft_id=payload.draft_id,
            descriptions_search=payload.descriptions_search,
        ),
        arguments=payload.model_dump(mode="json"),
    )
