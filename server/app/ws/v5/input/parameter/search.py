"""Input: parameter.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.parameter.search import search_parameter_impl

internal_sio = get_internal_sio()


class ParameterSearchPayload(BaseModel):
    """Payload for parameter.search socket event."""

    search: str | None = Field(None)
    scenario_ids: list[UUID] | None = Field(None)
    field_ids: list[UUID] | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    scenario_search: str | None = Field(None)
    field_search: str | None = Field(None)
    department_search: str | None = Field(None)
    page_size: int = Field(12)
    page_offset: int = Field(0)


@sio.on("parameter.search")  # type: ignore
async def parameter_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ParameterSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("parameter.search.failed", {
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
        artifact="parameter",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_parameter_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            scenario_ids=payload.scenario_ids,
            field_ids=payload.field_ids,
            filter_department_ids=payload.filter_department_ids,
            scenario_search=payload.scenario_search,
            field_search=payload.field_search,
            department_search=payload.department_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
