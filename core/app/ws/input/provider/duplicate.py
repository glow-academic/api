"""Input: provider.duplicate"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.provider.duplicate import duplicate_provider_impl
from app.infra.provider.types import DuplicateProviderApiRequest

internal_sio = get_internal_sio()


@sio.on("provider.duplicate")  # type: ignore
async def provider_duplicate(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DuplicateProviderApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("provider.duplicate.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    provider_id = payload.id or payload.provider_id
    if provider_id is None:
        await internal_sio.emit("provider.duplicate.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "Provider id is required (provide 'id' or legacy 'provider_id').",
            "error_type": "validation",
        })
        return

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="provider",
        operation="duplicate",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: duplicate_provider_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            id=provider_id,
            session_id=identity.session_id,
            accept=payload.accept,
            idempotency_key=payload.idempotency_key,
        ),
        arguments=payload.model_dump(mode="json"),
    )
