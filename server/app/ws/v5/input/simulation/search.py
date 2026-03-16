"""Input: simulation.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.simulation.search import search_simulation_impl

internal_sio = get_internal_sio()


class SimulationSearchPayload(BaseModel):
    """Payload for simulation.search socket event."""

    search: str | None = Field(None)
    filter_scenario_ids: list[UUID] | None = Field(None)
    filter_cohort_ids: list[UUID] | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    scenario_search: str | None = Field(None)
    cohort_search: str | None = Field(None)
    department_search: str | None = Field(None)
    flag_search: str | None = Field(None)
    page_size: int = Field(10)
    page_offset: int = Field(0)


@sio.on("simulation.search")  # type: ignore
async def simulation_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = SimulationSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("simulation.search.failed", {
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
        artifact="simulation",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_simulation_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            filter_scenario_ids=payload.filter_scenario_ids,
            filter_cohort_ids=payload.filter_cohort_ids,
            filter_department_ids=payload.filter_department_ids,
            scenario_search=payload.scenario_search,
            cohort_search=payload.cohort_search,
            department_search=payload.department_search,
            flag_search=payload.flag_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
