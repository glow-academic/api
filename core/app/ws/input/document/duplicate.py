"""Input: document.duplicate"""

from typing import Any

from app.infra.document.duplicate import duplicate_document_impl
from app.infra.document.types import DuplicateDocumentApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("document.duplicate")  # type: ignore
async def document_duplicate(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DuplicateDocumentApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("document.duplicate.failed", {
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
        operation="duplicate",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: duplicate_document_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            document_id=payload.document_id,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
