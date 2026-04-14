"""Input: dashboard.group"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.dashboard.group import (
    GroupDashboardApiRequest,
    group_dashboard_impl,
)


@sio.on("dashboard.group")  # type: ignore
async def dashboard_group(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GroupDashboardApiRequest(**data)
    except Exception:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="dashboard",
        operation="group",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: group_dashboard_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
