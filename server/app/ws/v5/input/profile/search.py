"""Input: profile.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.profile.search import search_profile_impl

internal_sio = get_internal_sio()


class ProfileSearchPayload(BaseModel):
    """Payload for profile.search socket event."""

    search: str | None = Field(None)
    cohort_ids: list[UUID] | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    role_filter: str | None = Field(None)
    cohort_search: str | None = Field(None)
    department_search: str | None = Field(None)
    role_search: str | None = Field(None)
    page_size: int = Field(12)
    page_offset: int = Field(0)


@sio.on("profile.search")  # type: ignore
async def profile_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ProfileSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("profile.search.failed", {
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
        artifact="profile",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_profile_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            cohort_ids=payload.cohort_ids,
            filter_department_ids=payload.filter_department_ids,
            role_filter=payload.role_filter,
            cohort_search=payload.cohort_search,
            department_search=payload.department_search,
            role_search=payload.role_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
