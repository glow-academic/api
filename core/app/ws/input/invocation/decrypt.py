"""Input: invocation.decrypt"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.invocation.decrypt import decrypt_invocation_impl
from app.infra.invocation.types import DecryptInvocationKeyApiRequest

internal_sio = get_internal_sio()


@sio.on("invocation.decrypt")  # type: ignore
async def invocation_decrypt(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DecryptInvocationKeyApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("invocation.decrypt.failed", {
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
        operation="decrypt",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: decrypt_invocation_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            invocation_id=payload.invocation_id,
            key_id=payload.key_id,
            bypass_cache=data.get("bypass_cache", False),
        ),
        arguments=payload.model_dump(mode="json"),
    )
