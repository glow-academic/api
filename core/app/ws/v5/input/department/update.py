"""Input: department.update"""

from typing import Any

from app.infra.department.types import UpdateDepartmentApiRequest
from app.infra.department.update import update_department_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("department.update")  # type: ignore
async def department_update(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = UpdateDepartmentApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("department.update.failed", {
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
        artifact="department",
        operation="update",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: update_department_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            items=payload.departments,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
