"""Input: department.duplicate"""

from typing import Any

from app.infra.department.duplicate import duplicate_department_impl
from app.infra.department.types import DuplicateDepartmentApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("department.duplicate")  # type: ignore
async def department_duplicate(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DuplicateDepartmentApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("department.duplicate.failed", {
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
        operation="duplicate",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: duplicate_department_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            department_id=payload.department_id,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
