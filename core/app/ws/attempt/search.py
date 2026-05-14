"""Input: attempt.search"""

from typing import Any

from app.infra.attempt.search import search_attempt_impl
from app.infra.attempt.types import SearchAttemptApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("attempt.search")  # type: ignore
async def attempt_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = SearchAttemptApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("attempt.search.failed", {
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
        artifact="attempt",
        operation="search",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        runner=lambda: search_attempt_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            target_profile_id=payload.target_profile_id,
            profile_ids=payload.profile_ids,
            cohort_ids=payload.cohort_ids,
            department_ids=payload.department_ids,
            role_ids=payload.role_ids,
            simulation_ids=payload.simulation_ids,
            scenario_ids=payload.scenario_ids,
            practice=payload.practice,
            infinite_mode=payload.infinite_mode,
            show_archived=payload.show_archived,
            start_date=payload.start_date,
            end_date=payload.end_date,
            simulation_search=payload.simulation_search,
            scenario_search=payload.scenario_search,
            profile_search=payload.profile_search,
            sort_by=payload.sort_by,
            sort_order=payload.sort_order,
            page=payload.page,
            page_size=payload.page_size,
        ),
        arguments=payload.model_dump(mode="json"),
    )
