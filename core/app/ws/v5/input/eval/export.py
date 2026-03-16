"""Input: eval.export"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.eval.export import export_eval_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class EvalExportPayload(BaseModel):
    """Payload for eval.export socket event."""

    eval_id: UUID | None = Field(None)


@sio.on("eval.export")  # type: ignore
async def eval_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = EvalExportPayload(**data)
    except Exception as e:
        await internal_sio.emit("eval.export.failed", {
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
        artifact="eval",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_eval_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            eval_id=payload.eval_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
