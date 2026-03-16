"""Input: model.search"""

from typing import Any

from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.model.search import search_model_impl

internal_sio = get_internal_sio()


class ModelSearchPayload(BaseModel):
    """Payload for model.search socket event."""

    search: str | None = Field(None)
    filter_provider_ids: list[UUID] | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    filter_agent_ids: list[UUID] | None = Field(None)
    provider_search: str | None = Field(None)
    department_search: str | None = Field(None)
    agent_search: str | None = Field(None)
    page_size: int = Field(12)
    page_offset: int = Field(0)


@sio.on("model.search")  # type: ignore
async def model_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ModelSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("model.search.failed", {
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
        artifact="model",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_model_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            filter_provider_ids=payload.filter_provider_ids,
            filter_department_ids=payload.filter_department_ids,
            filter_agent_ids=payload.filter_agent_ids,
            provider_search=payload.provider_search,
            department_search=payload.department_search,
            agent_search=payload.agent_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
