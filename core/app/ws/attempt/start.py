"""Input: attempt.start"""

from typing import Any

from app.infra.attempt.start import (
    AttemptStartRequest,
    AttemptStartResponse,
    attempt_start_impl,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("attempt.start")  # type: ignore
async def attempt_start(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = AttemptStartRequest(**data)
    except Exception:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="start",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: attempt_start_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
        response_model=AttemptStartResponse,
    )
