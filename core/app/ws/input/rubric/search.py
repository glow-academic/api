"""Input: rubric.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.rubric.search import search_rubric_impl

internal_sio = get_internal_sio()


class RubricSearchPayload(BaseModel):
    """Payload for rubric.search socket event."""

    search: str | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    filter_simulation_ids: list[UUID] | None = Field(None)
    department_search: str | None = Field(None)
    simulation_search: str | None = Field(None)
    page_size: int = Field(12)
    page_offset: int = Field(0)


@sio.on("rubric.search")  # type: ignore
async def rubric_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = RubricSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("rubric.search.failed", {
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
        artifact="rubric",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_rubric_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            filter_department_ids=payload.filter_department_ids,
            filter_simulation_ids=payload.filter_simulation_ids,
            department_search=payload.department_search,
            simulation_search=payload.simulation_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
