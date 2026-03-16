"""Input: activity.search"""

from typing import Any

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.routes.v5.activity.search import search_activity as search_activity_route

internal_sio = get_internal_sio()


# NOTE: activity search is inline in the route, not in infra.
# The socket handler imports the ListActivityRequest type and calls the
# route-level context resolver directly. For now we forward the payload
# via the audit wrapper with a thin runner that mirrors the HTTP route.

from app.infra.activity.context import resolve_activity_search_context
from app.infra.activity.types import ListActivityRequest, ListActivityResponse
from app.infra.common_context import resolve_common_context
from app.infra.session.types import SessionListItem


class ActivitySearchPayload(BaseModel):
    """Payload for activity.search socket event."""

    date_from: str | None = Field(None)
    date_to: str | None = Field(None)
    department_ids: list[str] | None = Field(None)
    roles: list[str] | None = Field(None)
    active: bool | None = Field(None)
    page: int = Field(0)
    page_size: int = Field(50)
    sort_order: str = Field("desc")


@sio.on("activity.search")  # type: ignore
async def activity_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ActivitySearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("activity.search.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    request = ListActivityRequest(
        date_from=payload.date_from,
        date_to=payload.date_to,
        department_ids=payload.department_ids or [],
        roles=payload.roles or [],
        active=payload.active,
        page=payload.page,
        page_size=payload.page_size,
        sort_order=payload.sort_order,
    )

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="activity",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: _run_search(pool, redis, identity.profile_id, request),
        arguments=payload.model_dump(mode="json"),
    )


async def _run_search(pool, redis, profile_id, request: ListActivityRequest):
    """Thin runner that mirrors the HTTP search route logic."""
    from collections import defaultdict
    from decimal import Decimal
    from uuid import UUID

    common = await resolve_common_context(
        pool, redis, profile_id=profile_id,
    )
    if not common:
        raise ValueError("Profile not found")

    ctx = await resolve_activity_search_context(
        pool,
        redis,
        department_ids=request.department_ids or None,
        roles=request.roles or None,
        date_from=request.date_from,
        date_to=request.date_to,
        active=request.active,
        sort_order=request.sort_order,
        page=request.page,
        page_size=request.page_size,
    )

    sessions = ctx.entries.get("sessions", [])
    total_sessions = ctx.entries.get("total_sessions", [])
    groups = ctx.entries.get("groups", [])
    runs = ctx.entries.get("runs", [])

    names_rp = ctx.resources.get("names")
    name_list = names_rp.selected if names_rp else []
    pricing_rp = ctx.resources.get("pricing")
    pricing_list = pricing_rp.selected if pricing_rp else []

    pricing_map: dict[UUID, dict] = {}
    for p in pricing_list:
        if p.id:
            pricing_map[p.id] = {
                "price": Decimal(str(p.price)) if p.price is not None else Decimal("0"),
                "unit_value": p.unit_value or 1,
            }

    name_map = {item.id: item.name for item in name_list if item.id and item.name}

    group_to_session: dict[UUID, UUID] = {}
    group_counts: dict[UUID, int] = defaultdict(int)
    for g in groups:
        if g.session_id:
            group_to_session[g.id] = g.session_id
            group_counts[g.session_id] += 1

    session_stats: dict[UUID, dict] = defaultdict(
        lambda: {
            "run_count": 0,
            "total_tokens": 0,
            "total_cost": Decimal("0"),
            "first_run_at": None,
            "last_run_at": None,
        }
    )

    for run in runs:
        sid_val = group_to_session.get(run.group_id) if run.group_id else None
        if not sid_val:
            continue
        stats = session_stats[sid_val]
        stats["run_count"] += 1
        stats["total_tokens"] += (
            run.input_tokens + run.output_tokens + run.cached_input_tokens
        )

        run_cost = Decimal("0")
        for p in run.pricing:
            if p.pricing_id and p.count:
                info = pricing_map.get(p.pricing_id)
                if info and info["unit_value"] > 0:
                    run_cost += (
                        Decimal(str(p.count)) / Decimal(str(info["unit_value"]))
                    ) * info["price"]
        stats["total_cost"] += run_cost

        if run.run_created_at:
            if stats["first_run_at"] is None or run.run_created_at < stats["first_run_at"]:
                stats["first_run_at"] = run.run_created_at
            if stats["last_run_at"] is None or run.run_created_at > stats["last_run_at"]:
                stats["last_run_at"] = run.run_created_at

    items: list[SessionListItem] = []
    for session in sessions:
        s_id = session.id
        stats = session_stats.get(s_id, {})

        items.append(
            SessionListItem(
                session_id=s_id,
                profile_id=session.profile_id,
                profile_name=name_map.get(session.profile_id) if session.profile_id else None,
                session_created_at=session.created_at,
                active=session.active,
                group_count=group_counts.get(s_id, 0),
                run_count=stats.get("run_count", 0),
                first_run_at=stats.get("first_run_at"),
                last_run_at=stats.get("last_run_at"),
                total_tokens=stats.get("total_tokens", 0),
                total_cost=stats.get("total_cost", Decimal("0")),
            )
        )

    total_count = len(total_sessions)
    page_size = request.page_size
    total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0

    return ListActivityResponse(
        data=items,
        total_count=total_count,
        page=request.page,
        page_size=page_size,
        total_pages=total_pages,
    )
