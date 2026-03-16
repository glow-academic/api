"""Input: department.get"""

from typing import Any

from app.infra.department.get import get_department_impl
from app.infra.department.types import GetDepartmentApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("department.get")  # type: ignore
async def department_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetDepartmentApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("department.get.failed", {
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
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_department_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            department_id=payload.department_id,
            draft_id=payload.draft_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
