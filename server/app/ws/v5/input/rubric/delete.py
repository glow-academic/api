"""Input: rubric.delete"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.rubric.delete import delete_rubric_impl
from app.infra.rubric.types import DeleteRubricApiRequest

internal_sio = get_internal_sio()


@sio.on("rubric.delete")  # type: ignore
async def rubric_delete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DeleteRubricApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("rubric.delete.failed", {
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
        operation="delete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: delete_rubric_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            rubric_ids=payload.rubric_ids,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
