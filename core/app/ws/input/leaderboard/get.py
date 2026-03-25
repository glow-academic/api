"""Input: leaderboard.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.leaderboard.get import get_leaderboard_impl_cached
from app.infra.leaderboard.types import LeaderboardRequest

internal_sio = get_internal_sio()


@sio.on("leaderboard.get")  # type: ignore
async def leaderboard_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = LeaderboardRequest(**data)
    except Exception as e:
        await internal_sio.emit("leaderboard.get.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    async def _runner():
        response_data, _cache_hit = await get_leaderboard_impl_cached(
            pool,
            payload,
            profile_id=identity.profile_id,
        )
        return response_data

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="leaderboard",
        operation="get",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments=payload.model_dump(mode="json"),
    )
