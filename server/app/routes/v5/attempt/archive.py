"""Attempts bulk archive endpoint."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.infra.globals import get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.attempt.search import search_attempts
from app.tools.entries.attempt_archive.create import create_attempt_archive
from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


class ArchiveAttemptsRequest(BaseModel):
    archived: bool = Field(..., description="Whether to archive (true) or unarchive (false)")
    attempt_ids: list[UUID] | None = Field(default_factory=list, description="Specific attempt UUIDs to archive")  # type: ignore[arg-type]
    start_date: str | None = Field(None, description="Start date for filter-based archive")
    end_date: str | None = Field(None, description="End date for filter-based archive")
    cohort_ids: list[UUID] | None = Field(default_factory=list, description="Cohort UUIDs to filter by")  # type: ignore[arg-type]
    department_ids: list[UUID] | None = Field(default_factory=list, description="Department UUIDs to filter by")  # type: ignore[arg-type]
    simulation_ids: list[UUID] | None = Field(default_factory=list, description="Simulation UUIDs to filter by")  # type: ignore[arg-type]
    scenario_ids: list[UUID] | None = Field(default_factory=list, description="Scenario UUIDs to filter by")  # type: ignore[arg-type]
    profile_ids_filter: list[UUID] | None = Field(default_factory=list, description="Profile UUIDs to filter by")  # type: ignore[arg-type]
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")


class ArchiveAttemptsResponse(BaseModel):
    updated_count: int = Field(0, description="Number of attempts updated")
    profile_ids_to_invalidate: list[str] | None = Field(None, description="Profile IDs whose caches need invalidation")


@router.post("/archive", response_model=ArchiveAttemptsResponse)
async def archive_attempts(
    request: ArchiveAttemptsRequest,
    http_request: Request,
    response: Response,
) -> ArchiveAttemptsResponse:
    """Bulk archive or unarchive attempts (simulation or benchmark)."""
    tags = ["attempts"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="Session ID is required.",
            )

        has_attempt_ids = request.attempt_ids and len(request.attempt_ids) > 0
        if not has_attempt_ids and (not request.start_date or not request.end_date):
            raise HTTPException(
                status_code=400,
                detail="start_date and end_date are required when using filter-based archive",
            )

        # 1. Resolve attempt IDs via search
        date_from = (
            datetime.fromisoformat(request.start_date) if request.start_date else None
        )
        date_to = datetime.fromisoformat(request.end_date) if request.end_date else None

        pool = get_pool()
        redis = get_redis_client()
        identity = await resolve_profile_identity_context(
            pool,
            profile_id,
            redis,
            session_id=session_id,
        )
        profiles_id = identity.profiles_id if identity else None
        group_id = identity.group_id if identity else None
        if group_id is None:
            raise HTTPException(
                status_code=400, detail="Group ID could not be resolved"
            )

        async with pool.acquire() as conn:
            attempts, _ = await search_attempts(
                conn,
                attempt_ids=request.attempt_ids or None,
                simulation_ids=request.simulation_ids or None,
                profile_ids=request.profile_ids_filter or None,
                cohort_ids=request.cohort_ids or None,
                department_ids=request.department_ids or None,
                scenario_ids=request.scenario_ids or None,
                infinite_mode=request.infinite_mode,
                date_from=date_from,
                date_to=date_to,
                limit=10000,
                offset=0,
            )

            if not attempts:
                return ArchiveAttemptsResponse(
                    updated_count=0, profile_ids_to_invalidate=[]
                )

            # 2. Create run + call for traceability
            run = await create_run(
                conn,
                group_id=group_id,
                session_id=session_id,
                profiles_id=profiles_id,
            )
            call = await create_call(
                conn,
                run_id=run.id,
                session_id=session_id,
            )

            # 3. Create archive entries
            for attempt in attempts:
                await create_attempt_archive(
                    conn,
                    attempt_id=attempt.attempt_id,
                    call_id=call.id,
                    archived=request.archived,
                )

        # 4. Collect profile IDs to invalidate (from search results)
        profile_ids_to_invalidate = list(
            {str(a.profile_id) for a in attempts if a.profile_id}
        )

        # 5. Invalidate cache
        invalidation_tags = tags + ["dashboard"]
        for pid in profile_ids_to_invalidate:
            invalidation_tags.extend(
                [
                    f"home:profile:{pid}",
                    f"reports:profile:{pid}",
                    f"practice:profile:{pid}",
                    f"history:profile:{pid}",
                ]
            )

        await invalidate_tags(invalidation_tags, redis=get_redis_client())
        response.headers["X-Invalidate-Tags"] = ",".join(invalidation_tags)

        return ArchiveAttemptsResponse(
            updated_count=len(attempts),
            profile_ids_to_invalidate=profile_ids_to_invalidate,
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="archive_attempts",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
