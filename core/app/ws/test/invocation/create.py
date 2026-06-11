"""Input: test.invocation_create — canonical WS handler.

Mirrors the HTTP ``POST /test/invocation_create`` route: materializes a
test_invocation_entry through the audit framework so
``test.invocation_create.completed`` (the event the client's WS command
channel awaits) flows back over Socket.IO. Without this handler the
client-emitted ``test.invocation_create`` event had no ``sio.on`` listener
and the client hung for the full 30s command timeout.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.invocation.create import (
    CreateInvocationApiRequest,
    CreateInvocationApiResponse,
    create_invocation_impl,
)


@sio.on("test.invocation_create")  # type: ignore
async def test_invocation_create(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = CreateInvocationApiRequest(**data)
    except Exception:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="test",
        operation="invocation_create",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: create_invocation_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
        response_model=CreateInvocationApiResponse,
        operation_key=payload.idempotency_key,
        upload_folder=get_upload_folder(),
    )
