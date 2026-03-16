"""Input: record.get"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.reports.get import get_reports_impl
from app.infra.reports.types import ReportsRequest

internal_sio = get_internal_sio()


class RecordGetPayload(BaseModel):
    """Payload for record.get socket event."""

    target_profile_id: UUID = Field(...)
    start_date: str | None = Field(None)
    end_date: str | None = Field(None)
    cohort_ids: list[UUID] | None = Field(None)
    simulation_ids: list[UUID] | None = Field(None)
    department_ids: list[UUID] | None = Field(None)
    simulation_filters: list[str] | None = Field(None)
    actor_profile_id: UUID | None = Field(None)
    rubric_ids: list[UUID] | None = Field(None)
    rubric_search: str | None = Field(None)
    simulation_picker_ids: list[UUID] | None = Field(None)
    simulation_picker_search: str | None = Field(None)
    parameter_ids: list[UUID] | None = Field(None)
    parameter_search: str | None = Field(None)
    scenario_ids: list[UUID] | None = Field(None)
    scenario_search: str | None = Field(None)


@sio.on("record.get")  # type: ignore
async def record_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = RecordGetPayload(**data)
    except Exception as e:
        await internal_sio.emit("record.get.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    # Record get uses reports impl scoped to a single profile
    request = ReportsRequest(
        start_date=payload.start_date,
        end_date=payload.end_date,
        cohort_ids=payload.cohort_ids,
        simulation_ids=payload.simulation_ids,
        department_ids=payload.department_ids,
        simulation_filters=payload.simulation_filters,
        actor_profile_id=payload.actor_profile_id,
        target_profile_id=payload.target_profile_id,
        scenario_ids=payload.scenario_ids,
    )

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="record",
        operation="get",
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
