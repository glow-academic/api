"""Input: parameter.update"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.parameter.types import UpdateParameterApiRequest
from app.infra.parameter.update import update_parameter_impl

internal_sio = get_internal_sio()


@sio.on("parameter.update")  # type: ignore
async def parameter_update(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = UpdateParameterApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("parameter.update.failed", {
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
        artifact="parameter",
        operation="update",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: update_parameter_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            items=payload.parameters,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
