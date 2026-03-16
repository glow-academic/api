"""Input: record.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.reports.get import get_reports_impl
from app.infra.reports.types import ReportsRequest

internal_sio = get_internal_sio()


class RecordSearchPayload(BaseModel):
    """Payload for record.search socket event."""

    target_profile_id: UUID = Field(...)
    start_date: str | None = Field(None)
    end_date: str | None = Field(None)
    cohort_ids: list[UUID] | None = Field(None)
    department_ids: list[UUID] | None = Field(None)
    practice: bool = Field(False)
    scenario_ids: list[UUID] | None = Field(None)
    infinite_mode: bool | None = Field(None)
    show_archived: bool = Field(False)
    sort_by: str = Field("date")
    sort_order: str = Field("desc")
    page: int = Field(0)
    page_size: int = Field(20)
    simulation_search: str | None = Field(None)
    scenario_search: str | None = Field(None)


@sio.on("record.search")  # type: ignore
async def record_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = RecordSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("record.search.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    # Record search reuses the reports impl scoped to a single profile
    request = ReportsRequest(
        start_date=payload.start_date,
        end_date=payload.end_date,
        cohort_ids=payload.cohort_ids,
        department_ids=payload.department_ids,
        target_profile_id=payload.target_profile_id,
        scenario_ids=payload.scenario_ids,
        sort_by=payload.sort_by,
        sort_order=payload.sort_order,
        page_limit=payload.page_size,
        page_offset=payload.page,
    )

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="record",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_reports_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            request=request,
        ),
        arguments=payload.model_dump(mode="json"),
    )
