"""Input: rubric.export"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.rubric.export import export_rubric_impl

internal_sio = get_internal_sio()


class RubricExportPayload(BaseModel):
    """Payload for rubric.export socket event."""

    rubric_id: UUID | None = Field(None)


@sio.on("rubric.export")  # type: ignore
async def rubric_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = RubricExportPayload(**data)
    except Exception as e:
        await internal_sio.emit("rubric.export.failed", {
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
        artifact="rubric",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_rubric_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            rubric_id=payload.rubric_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
