"""Input: field.delete"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.field.delete import delete_field_impl
from app.infra.field.types import DeleteFieldApiRequest
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("field.delete")  # type: ignore
async def field_delete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DeleteFieldApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("field.delete.failed", {
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
        artifact="field",
        operation="delete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: delete_field_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            field_ids=payload.field_ids,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
