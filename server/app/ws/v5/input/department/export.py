"""Input: department.export"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.department.export import export_department_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class DepartmentExportPayload(BaseModel):
    """Payload for department.export socket event."""

    department_id: UUID | None = Field(None)


@sio.on("department.export")  # type: ignore
async def department_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DepartmentExportPayload(**data)
    except Exception as e:
        await internal_sio.emit("department.export.failed", {
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
        artifact="department",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_department_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            department_id=payload.department_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
