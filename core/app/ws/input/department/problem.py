"""Input: department.problem"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.department.problem import problem_department_impl
from app.infra.department.types import ProblemDepartmentApiRequest

internal_sio = get_internal_sio()


@sio.on("department.problem")  # type: ignore
async def department_problem(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ProblemDepartmentApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("department.problem.failed", {
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
        operation="problem",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: problem_department_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            type=payload.type,
            message=payload.message,
            accept=payload.accept,
            idempotency_key=payload.idempotency_key,
        ),
        arguments=payload.model_dump(mode="json"),
    )
