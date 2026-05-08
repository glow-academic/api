"""Input: invocation.export"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.invocation.export import export_invocation_impl
from app.infra.test.group import group_test_impl

internal_sio = get_internal_sio()


class InvocationExportPayload(BaseModel):
    """Payload for invocation.export socket event."""

    test_id: UUID
    invocation_entry_id: UUID | None = Field(None)
    draft_id: UUID | None = Field(None)


@sio.on("test.invocation.export")  # type: ignore
async def invocation_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = InvocationExportPayload(**data)
    except Exception as e:
        await internal_sio.emit("test.invocation_export.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    # Canonical group for test artifact — threaded to export_invocation_impl.
    group_result = await group_test_impl(
        pool, redis,
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        include_history=False,
    )
    group_id = group_result.group_id

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="test",
        operation="invocation_export",
        profile_id=identity.profile_id,
        sid=sid,
        runner=lambda: export_invocation_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            test_id=payload.test_id,
            group_id=group_id,
            invocation_entry_id=payload.invocation_entry_id,
            draft_id=payload.draft_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
