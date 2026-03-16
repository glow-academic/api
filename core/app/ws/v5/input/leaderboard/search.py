"""Input: leaderboard.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.leaderboard.get import get_leaderboard_impl_cached
from app.infra.leaderboard.types import LeaderboardRequest

internal_sio = get_internal_sio()


class LeaderboardSearchPayload(BaseModel):
    """Payload for leaderboard.search socket event."""

    start_date: str | None = Field(None)
    end_date: str | None = Field(None)
    cohort_ids: list[UUID] | None = Field(None)
    department_ids: list[UUID] | None = Field(None)
    simulation_filters: list[str] | None = Field(None)
    target_profile_id: UUID | None = Field(None)
    cohort_id: UUID | None = Field(None)


@sio.on("leaderboard.search")  # type: ignore
async def leaderboard_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = LeaderboardSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("leaderboard.search.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    request = LeaderboardRequest(
        start_date=payload.start_date,
        end_date=payload.end_date,
        cohort_ids=payload.cohort_ids,
        department_ids=payload.department_ids,
        simulation_filters=payload.simulation_filters,
        target_profile_id=payload.target_profile_id,
        cohort_id=payload.cohort_id,
    )

    async def _runner():
        response_data, _cache_hit = await get_leaderboard_impl_cached(
            pool,
            request,
            profile_id=identity.profile_id,
        )
        return response_data

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="leaderboard",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=_runner,
        arguments=payload.model_dump(mode="json"),
    )
