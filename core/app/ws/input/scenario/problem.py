"""Input: scenario.problem"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.scenario.problem import problem_scenario_impl
from app.infra.scenario.types import ProblemScenarioApiRequest

internal_sio = get_internal_sio()


@sio.on("scenario.problem")  # type: ignore
async def scenario_problem(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ProblemScenarioApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("scenario.problem.failed", {
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
        artifact="scenario",
        operation="problem",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: problem_scenario_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            type=payload.type,
            message=payload.message,
        ),
        arguments=payload.model_dump(mode="json"),
    )
