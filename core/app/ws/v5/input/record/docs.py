"""Input: record.docs"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.record_docs import docs_record_client

internal_sio = get_internal_sio()


class RecordDocsPayload(BaseModel):
    """Payload for record.docs socket event."""

    entity_id: UUID | None = Field(None)


@sio.on("record.docs")  # type: ignore
async def record_docs(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = RecordDocsPayload(**data)
    except Exception as e:
        await internal_sio.emit("record.docs.failed", {
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
        artifact="record",
        operation="docs",
        profile_id=identity.profile_id,
        entity_id=payload.entity_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: docs_record_client(
            pool,
            redis,
            profile_id=identity.profile_id,
            entity_id=payload.entity_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
