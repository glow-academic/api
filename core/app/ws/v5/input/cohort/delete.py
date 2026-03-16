"""Input: cohort.delete"""

from typing import Any

from app.infra.cohort.delete import delete_cohort_impl
from app.infra.cohort.types import DeleteCohortApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("cohort.delete")  # type: ignore
async def cohort_delete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DeleteCohortApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("cohort.delete.failed", {
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
        artifact="cohort",
        operation="delete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: delete_cohort_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            cohort_ids=payload.cohort_ids,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
