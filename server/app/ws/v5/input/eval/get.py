"""Input: eval.get"""

from typing import Any

from app.infra.eval.get import get_eval_impl
from app.infra.eval.types import GetEvalApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("eval.get")  # type: ignore
async def eval_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetEvalApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("eval.get.failed", {
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
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_eval_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            eval_id=payload.eval_id,
            draft_id=payload.draft_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
