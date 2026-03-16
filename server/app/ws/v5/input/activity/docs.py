"""Input: activity.docs"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.activity.docs import docs_activity_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class ActivityDocsPayload(BaseModel):
    """Payload for activity.docs socket event."""

    entity_id: UUID | None = Field(None)


@sio.on("activity.docs")  # type: ignore
async def activity_docs(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ActivityDocsPayload(**data)
    except Exception as e:
        await internal_sio.emit("activity.docs.failed", {
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
        artifact="activity",
        operation="docs",
        profile_id=identity.profile_id,
        entity_id=payload.entity_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: docs_activity_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            entity_id=payload.entity_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
