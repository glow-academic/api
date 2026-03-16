"""Input: provider.update"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.provider.types import UpdateProviderApiRequest
from app.infra.provider.update import update_provider_impl

internal_sio = get_internal_sio()


@sio.on("provider.update")  # type: ignore
async def provider_update(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = UpdateProviderApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("provider.update.failed", {
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
        artifact="provider",
        operation="update",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: update_provider_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            items=payload.providers,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
