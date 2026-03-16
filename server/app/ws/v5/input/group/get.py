"""Input: group.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.group.get import get_group_impl
from app.infra.group.types import GetGroupDetailRequest
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("group.get")  # type: ignore
async def group_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetGroupDetailRequest(**data)
    except Exception as e:
        await internal_sio.emit("group.get.failed", {
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
        artifact="group",
        operation="get",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_group_impl(
            pool,
            profile_id=identity.profile_id,
            group_id=payload.group_id,
            redis=redis,
            message_limit=payload.message_limit,
            message_offset=payload.message_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
