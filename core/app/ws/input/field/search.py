"""Input: field.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.field.search import search_field_impl
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class FieldSearchPayload(BaseModel):
    """Payload for field.search socket event."""

    search: str | None = Field(None)
    parameter_ids: list[UUID] | None = Field(None)
    persona_ids: list[UUID] | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    parameter_search: str | None = Field(None)
    persona_search: str | None = Field(None)
    department_search: str | None = Field(None)
    page_size: int = Field(12)
    page_offset: int = Field(0)


@sio.on("field.search")  # type: ignore
async def field_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = FieldSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("field.search.failed", {
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
        artifact="field",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_field_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            parameter_ids=payload.parameter_ids,
            persona_ids=payload.persona_ids,
            filter_department_ids=payload.filter_department_ids,
            parameter_search=payload.parameter_search,
            persona_search=payload.persona_search,
            department_search=payload.department_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
