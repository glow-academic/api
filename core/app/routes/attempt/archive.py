"""POST /attempt/archive — thin HTTP adapter over archive_attempt_impl."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.attempt.archive import (
    ArchiveAttemptsRequest,
    ArchiveAttemptsResponse,
    MissingFilterError,
    archive_attempt_impl,
)
from app.infra.globals import get_pool, get_redis_client
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/archive", response_model=ArchiveAttemptsResponse)
async def archive_attempts(
    request: ArchiveAttemptsRequest,
    http_request: Request,
    response: Response,
) -> ArchiveAttemptsResponse:
    """Bulk archive or unarchive attempts (simulation or benchmark)."""
    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required.")

        try:
            result = await archive_attempt_impl(
                get_pool(),
                get_redis_client(),
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )
        except MissingFilterError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Cache invalidation — HTTP-only concern; not part of the impl contract.
        invalidation_tags = ["attempts", "dashboard"]
        for pid in result.profile_ids_to_invalidate or []:
            invalidation_tags.extend([
                f"home:profile:{pid}",
                f"reports:profile:{pid}",
                f"practice:profile:{pid}",
                f"history:profile:{pid}",
            ])
        await invalidate_tags(invalidation_tags, redis=get_redis_client())
        response.headers["X-Invalidate-Tags"] = ",".join(invalidation_tags)

        return result
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
