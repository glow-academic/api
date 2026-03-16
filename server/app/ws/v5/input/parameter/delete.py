"""Input: parameter.delete"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.parameter.delete import delete_parameter_impl
from app.infra.parameter.types import DeleteParameterApiRequest

internal_sio = get_internal_sio()


@sio.on("parameter.delete")  # type: ignore
async def parameter_delete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DeleteParameterApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("parameter.delete.failed", {
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
        operation="delete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: delete_parameter_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            parameter_ids=payload.parameter_ids,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
