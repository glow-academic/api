"""Input: cohort.drafts"""

from typing import Any

from app.infra.cohort.drafts import list_cohort_drafts_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity


@sio.on("cohort.drafts")  # type: ignore
async def cohort_drafts(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="cohort",
        operation="drafts",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: list_cohort_drafts_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
        ),
        arguments={},
    )
