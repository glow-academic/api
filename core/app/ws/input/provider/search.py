"""Input: provider.search"""

from typing import Any

from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.provider.search import search_provider_impl

internal_sio = get_internal_sio()


class ProviderSearchPayload(BaseModel):
    """Payload for provider.search socket event."""

    search: str | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    filter_model_ids: list[UUID] | None = Field(None)
    filter_status: list[str] | None = Field(None)
    department_search: str | None = Field(None)
    model_search: str | None = Field(None)
    page_size: int = Field(12)
    page_offset: int = Field(0)


@sio.on("provider.search")  # type: ignore
async def provider_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ProviderSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("provider.search.failed", {
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
        artifact="provider",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_provider_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            filter_department_ids=payload.filter_department_ids,
            filter_model_ids=payload.filter_model_ids,
            filter_status=payload.filter_status,
            department_search=payload.department_search,
            model_search=payload.model_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
