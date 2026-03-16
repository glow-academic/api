"""Input: document.update"""

from typing import Any

from app.infra.document.types import UpdateDocumentApiRequest
from app.infra.document.update import update_document_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("document.update")  # type: ignore
async def document_update(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = UpdateDocumentApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("document.update.failed", {
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
        artifact="document",
        operation="update",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: update_document_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            items=payload.documents,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
