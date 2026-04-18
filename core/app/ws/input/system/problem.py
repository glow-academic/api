"""Input: system.problem"""

from typing import Any

from app.infra.system.problem import problem_system_impl
from app.infra.system.types import ProblemSystemApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("system.problem")  # type: ignore
async def system_problem(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ProblemSystemApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("system.problem.failed", {
            "sid": sid, "rooms": [sid], "message": str(e), "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool, redis, artifact="system", operation="problem",
        profile_id=identity.profile_id, session_id=identity.session_id,
        sid=sid, rooms=[sid],
        runner=lambda: problem_system_impl(
            pool, redis, profile_id=identity.profile_id, session_id=identity.session_id,
            type=payload.type, message=payload.message,
        ),
        arguments=payload.model_dump(mode="json"),
    )
