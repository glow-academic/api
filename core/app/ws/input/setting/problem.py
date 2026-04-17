"""Input: setting.problem"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.setting.problem import problem_setting_impl
from app.infra.setting.types import ProblemSettingApiRequest

internal_sio = get_internal_sio()


@sio.on("setting.problem")  # type: ignore
async def setting_problem(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ProblemSettingApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("setting.problem.failed", {
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
        artifact="setting",
        operation="problem",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: problem_setting_impl(
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
