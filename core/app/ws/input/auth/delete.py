"""Input: auth.delete"""

from typing import Any

from app.infra.auth.delete import delete_auth_impl
from app.infra.auth.types import DeleteAuthApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("auth.delete")  # type: ignore
async def auth_delete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DeleteAuthApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("auth.delete.failed", {
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
        operation="delete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: delete_auth_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            auth_ids=payload.auth_ids,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
