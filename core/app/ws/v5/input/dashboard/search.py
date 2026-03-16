"""Input: dashboard.search"""

from typing import Any

from app.infra.dashboard.types import ListDashboardRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("dashboard.search")  # type: ignore
async def dashboard_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ListDashboardRequest(**data)
    except Exception as e:
        await internal_sio.emit("dashboard.search.failed", {
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
        artifact="dashboard",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: _run_search(pool, redis, identity.profile_id, payload),
        arguments=payload.model_dump(mode="json"),
    )


async def _run_search(pool, redis, profile_id, request: ListDashboardRequest):
    """Mirrors the HTTP dashboard search route logic."""
    from datetime import datetime
    from uuid import UUID

    from app.infra.common_context import resolve_common_context
    from app.infra.dashboard.context import resolve_dashboard_search_context
    from app.routes.v5.dashboard.search import _build_history_response

    common = await resolve_common_context(pool, redis, profile_id=profile_id)
    if not common:
        raise ValueError("Profile not found")

    profile_resource_id: UUID | None = None
    async with pool.acquire() as c:
        profile_resource_id = await c.fetchval(
            """
            SELECT profiles_id FROM profile_profiles_junction
            WHERE profile_id = $1 AND active = true
            LIMIT 1
            """,
            profile_id,
        )

    parsed_start_date = (
        datetime.fromisoformat(request.start_date.replace("Z", "+00:00"))
        if request.start_date
        else None
    )
    parsed_end_date = (
        datetime.fromisoformat(request.end_date.replace("Z", "+00:00"))
        if request.end_date
        else None
    )

    search_ctx = await resolve_dashboard_search_context(
        pool,
        redis,
        profile_resource_id=profile_resource_id,
        target_profile_id=request.target_profile_id,
        cohort_ids=request.cohort_ids,
        department_ids=request.department_ids,
        practice=request.practice,
        scenario_ids=request.scenario_ids,
        infinite_mode=request.infinite_mode,
        show_archived=request.show_archived,
        sort_by=request.sort_by,
        sort_order=request.sort_order,
        page=request.page,
        page_size=request.page_size,
        date_from=parsed_start_date.date() if parsed_start_date else None,
        date_to=parsed_end_date.date() if parsed_end_date else None,
    )

    return _build_history_response(
        search_ctx,
        practice=request.practice,
        simulation_search=request.simulation_search,
        scenario_search=request.scenario_search,
        profile_search=request.profile_search,
        page=request.page,
        page_size=request.page_size,
    )
