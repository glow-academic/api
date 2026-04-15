"""Input: tool.problem"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.tool.problem import problem_tool_impl
from app.infra.tool.types import ProblemToolApiRequest

internal_sio = get_internal_sio()


@sio.on("tool.problem")  # type: ignore
async def tool_problem(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ProblemToolApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("tool.problem.failed", {
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
        artifact="tool",
        operation="problem",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: problem_tool_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            type=payload.type,
            message=payload.message,
        ),
        arguments=payload.model_dump(mode="json"),
    )
