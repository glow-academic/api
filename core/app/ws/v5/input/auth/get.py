"""Input: auth.get"""

from typing import Any

from app.infra.auth.get import get_auth_impl
from app.infra.auth.types import GetAuthApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("auth.get")  # type: ignore
async def auth_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetAuthApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("auth.get.failed", {
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
        artifact="auth",
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_auth_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            auth_id=payload.auth_id,
            draft_id=payload.draft_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
