"""Input: auth.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.auth.search import search_auth_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class AuthSearchPayload(BaseModel):
    """Payload for auth.search socket event."""

    search: str | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    department_search: str | None = Field(None)
    page_size: int = Field(1000)
    page_offset: int = Field(0)


@sio.on("auth.search")  # type: ignore
async def auth_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = AuthSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("auth.search.failed", {
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
        artifact="auth",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_auth_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            filter_department_ids=payload.filter_department_ids,
            department_search=payload.department_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
