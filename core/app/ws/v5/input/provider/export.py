"""Input: provider.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.provider.export import export_provider_impl
from app.infra.provider.types import ExportProviderApiRequest

internal_sio = get_internal_sio()


@sio.on("provider.export")  # type: ignore
async def provider_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportProviderApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("provider.export.failed", {
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
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_provider_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            provider_id=payload.provider_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
