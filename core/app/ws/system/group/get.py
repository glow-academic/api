"""Input: system.group.get

Thin WS adapter over the canonical ``resolve_group_impl``. Replaces the
previous ``get_group_impl`` route (merged in 2026-05) — same response
shape (full detail tree with models/agents/profiles), single canonical
source.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.group.resolve import resolve_group_impl
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class _GroupGetRequest(BaseModel):
    """Validation-only request shape for the WS event."""

    group_id: UUID = Field(..., description="UUID of the group to fetch")


@sio.on("system.group")  # type: ignore
async def group_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = _GroupGetRequest(**data)
    except Exception as e:
        await internal_sio.emit("system.group_get.failed", {
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
        artifact="system",
        operation="group_get",
        profile_id=identity.profile_id,
        sid=sid,
        runner=lambda: resolve_group_impl(
            pool,
            redis,
            artifact_type="system",
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            group_id=payload.group_id,
            include_resources=True,
        ),
        arguments=payload.model_dump(mode="json"),
    )
