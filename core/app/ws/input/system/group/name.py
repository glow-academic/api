"""Input: group.name"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder, sio
from app.infra.group.name import name_group_impl
from app.infra.identity.socket import resolve_socket_identity


@sio.on("system.group.name")  # type: ignore
async def group_name(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()
    group_id = data.get("group_id")
    name = data.get("name", "")

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="system",
        operation="group_name",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        group_id=group_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: name_group_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            group_id=group_id,
            name=name,
        ),
        arguments=data,
        upload_folder=get_upload_folder(),
    )
