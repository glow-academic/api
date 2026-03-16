"""Input: persona.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.persona.export import export_persona_impl
from app.infra.persona.types import ExportPersonaApiRequest

internal_sio = get_internal_sio()


@sio.on("persona.export")  # type: ignore
async def persona_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportPersonaApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("persona.export.failed", {
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
        artifact="persona",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_persona_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            persona_id=payload.persona_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
