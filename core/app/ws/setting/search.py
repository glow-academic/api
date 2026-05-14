"""Input: setting.search"""

from typing import Any

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.setting.search import search_setting_impl


class SettingSearchPayload(BaseModel):
    """Payload for setting.search socket event."""

    flag_search: str | None = Field(None)


@sio.on("setting.search")  # type: ignore
async def setting_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    payload = SettingSearchPayload(**data)
    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="setting",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        runner=lambda: search_setting_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            flag_search=payload.flag_search,
        ),
        arguments=payload.model_dump(mode="json"),
    )
