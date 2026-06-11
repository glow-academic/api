"""Input: test.draft — canonical WS handler for the invocation draft.

Mirrors the HTTP ``POST /test/draft`` route (and ws/test/invocation/draft.py,
which serves the ``test.invocation_draft`` alias): patches the invocation
draft through the audit framework so ``test.draft.completed`` (the event the
client's WS command channel awaits) flows back over Socket.IO. Without this
handler the client-emitted ``test.draft`` event had no ``sio.on`` listener
and the client hung for the full 30s command timeout.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.invocation.draft import patch_invocation_draft_impl
from app.infra.invocation.types import PatchInvocationDraftApiRequest

internal_sio = get_internal_sio()


@sio.on("test.draft")  # type: ignore
async def test_draft(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = PatchInvocationDraftApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("test.draft.failed", {
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
        artifact="test",
        operation="draft",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: patch_invocation_draft_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
