"""Input: rubric.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.rubric.get import get_rubric_impl
from app.infra.rubric.types import GetRubricApiRequest

internal_sio = get_internal_sio()


@sio.on("rubric.get")  # type: ignore
async def rubric_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetRubricApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("rubric.get.failed", {
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
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_rubric_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            rubric_id=payload.rubric_id,
            draft_id=payload.draft_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
