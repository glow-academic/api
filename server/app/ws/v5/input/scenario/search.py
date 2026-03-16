"""Input: scenario.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.scenario.search import search_scenario_impl

internal_sio = get_internal_sio()


class ScenarioSearchPayload(BaseModel):
    """Payload for scenario.search socket event."""

    search: str | None = Field(None)
    persona_ids: list[UUID] | None = Field(None)
    simulation_ids: list[UUID] | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    persona_search: str | None = Field(None)
    simulation_search: str | None = Field(None)
    department_search: str | None = Field(None)
    flag_search: str | None = Field(None)
    page_size: int = Field(10)
    page_offset: int = Field(0)


@sio.on("scenario.search")  # type: ignore
async def scenario_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ScenarioSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("scenario.search.failed", {
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
        artifact="scenario",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_scenario_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            persona_ids=payload.persona_ids,
            simulation_ids=payload.simulation_ids,
            filter_department_ids=payload.filter_department_ids,
            persona_search=payload.persona_search,
            simulation_search=payload.simulation_search,
            department_search=payload.department_search,
            flag_search=payload.flag_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
