"""Input: invocation.export"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.invocation.export import export_invocation_impl
from app.infra.profile_identity_context import resolve_profile_identity_context

internal_sio = get_internal_sio()


class InvocationExportPayload(BaseModel):
    """Payload for invocation.export socket event."""

    test_id: UUID
    invocation_entry_id: UUID | None = Field(None)
    draft_id: UUID | None = Field(None)


@sio.on("invocation.export")  # type: ignore
async def invocation_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = InvocationExportPayload(**data)
    except Exception as e:
        await internal_sio.emit("invocation.export.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    # Resolve group_id like the HTTP route does
    pic = await resolve_profile_identity_context(
        pool,
        identity.profile_id,
        redis,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        test_id=payload.test_id,
    )
    group_id = pic.group_id if pic else None
    if group_id is None:
        await internal_sio.emit("invocation.export.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": "Group ID could not be resolved for invocation export",
            "error_type": "validation",
        })
        return

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="invocation",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
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
