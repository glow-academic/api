"""Input: field.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.field.get import get_field_impl
from app.infra.field.types import GetFieldApiRequest
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("field.get")  # type: ignore
async def field_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetFieldApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("field.get.failed", {
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
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_field_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            field_id=payload.field_id,
            draft_id=payload.draft_id,
            descriptions_search=payload.descriptions_search,
            conditional_parameter_search=payload.conditional_parameter_search,
            conditional_parameter_show_selected=payload.conditional_parameter_show_selected,
        ),
        arguments=payload.model_dump(mode="json"),
    )
