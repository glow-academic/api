"""Input: attempt.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.attempt.export import export_attempt_impl
from app.infra.attempt.types import ExportAttemptApiRequest

internal_sio = get_internal_sio()


@sio.on("attempt.export")  # type: ignore
async def attempt_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportAttemptApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("attempt.export.failed", {
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
        artifact="attempt",
        operation="export",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_attempt_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            attempt_id=payload.attempt_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
