"""Input: record.export"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.record_export import export_record_client

internal_sio = get_internal_sio()


class RecordExportPayload(BaseModel):
    """Payload for record.export socket event."""

    target_profile_id: UUID = Field(...)


@sio.on("record.export")  # type: ignore
async def record_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = RecordExportPayload(**data)
    except Exception as e:
        await internal_sio.emit("record.export.failed", {
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
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_record_client(
            pool,
            redis,
            profile_id=identity.profile_id,
            target_profile_id=payload.target_profile_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
