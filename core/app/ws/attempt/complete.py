"""Input: attempt.complete"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.attempt.complete import complete_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


class AttemptCompletePayload(BaseModel):
    attempt_id: UUID
    message: str = ""


@sio.on("attempt.complete")  # type: ignore
async def attempt_complete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = AttemptCompletePayload(**data)
    except Exception:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        operation="complete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: complete_attempt_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            attempt_id=payload.attempt_id,
            message=payload.message,
        ),
        arguments=payload.model_dump(mode="json"),
    )
