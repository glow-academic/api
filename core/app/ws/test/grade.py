"""Input: test.grade — canonical WS handler.

Mirrors the HTTP ``POST /test/grade`` route: records a test grade through
the audit framework so ``test.grade.completed`` (the event the client's WS
command channel awaits) flows back over Socket.IO. Without this handler the
client-emitted ``test.grade`` event had no ``sio.on`` listener and the
client hung for the full 30s command timeout.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.grade import create_grade_impl


class GradePayload(BaseModel):
    invocation_id: UUID
    run_id: UUID | None = None
    score: int = 0
    full: bool = False
    idempotency_key: UUID | None = None


@sio.on("test.grade")  # type: ignore
async def test_grade(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GradePayload(**data)
    except Exception:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="test",
        operation="grade",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: create_grade_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            invocation_id=payload.invocation_id,
            run_id=payload.run_id,
            score=payload.score,
            full=payload.full,
        ),
        arguments=payload.model_dump(mode="json"),
        operation_key=payload.idempotency_key,
        upload_folder=get_upload_folder(),
    )
