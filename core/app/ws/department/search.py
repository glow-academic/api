"""Input: department.search"""

from typing import Any

from pydantic import Field

from app.infra.department.search import search_department_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.ws.pagination import PaginatedWsSearch

internal_sio = get_internal_sio()


class DepartmentSearchPayload(PaginatedWsSearch):
    """Payload for department.search socket event."""

    search: str | None = Field(None)
    flag_search: str | None = Field(None)


@sio.on("department.search")  # type: ignore
async def department_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DepartmentSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("department.search.failed", {
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
        artifact="department",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        runner=lambda: search_department_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            flag_search=payload.flag_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
