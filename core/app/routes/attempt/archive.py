"""POST /attempt/archive — routed through the audit wrapper (idempotency + soft/accept)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.attempt.archive import (
    ArchiveAttemptsRequest,
    ArchiveAttemptsResponse,
    MissingFilterError,
    archive_attempt_impl,
)
from app.infra.attempt.cache_tags import build_attempt_profile_cache_tags
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


def build_attempt_archive_invalidation_tags(
    profile_ids: list[str] | None,
) -> list[str]:
    """HTTP cache tags to bust after an attempt archive/unarchive.

    Archiving an attempt flips its ``is_archived`` flag, which removes it
    from every default (non-archived) attempt-derived view. Those views are
    cached under the shared ``artifacts`` umbrella tag: the leaderboard
    bundle (``["artifacts", "leaderboard"]``), the record/profile report
    (``["artifacts", "record", ...]``), the session detail
    (``["artifacts", "session"]``) and the activity feed
    (``["artifacts", "activity"]``) — none of which carry ``dashboard`` or
    the per-profile ``home/practice/...`` tags. Busting ``artifacts`` here
    mirrors the sibling ``POST /test/archive`` route (which busts
    ``["benchmark", "test", "artifacts"]``) and the attempt run-complete /
    grade paths (``refresh_attempt_impl`` busts ``["attempt", "artifacts"]``).
    Without it the leaderboard/record caches keep serving the now-archived
    attempt for up to their 300s TTL.
    """
    tags = ["attempts", "dashboard", "artifacts"]
    for pid in profile_ids or []:
        # home:profile:{pid} + practice:profile:{pid} via the shared helper
        # (same construction the complete/grade/refresh path now busts).
        tags.extend(build_attempt_profile_cache_tags(pid))
        tags.extend([
            f"reports:profile:{pid}",
            f"history:profile:{pid}",
        ])
    return tags


@router.post("/archive", response_model=ArchiveAttemptsResponse)
async def archive_attempts(
    request: ArchiveAttemptsRequest,
    http_request: Request,
    response: Response,
) -> ArchiveAttemptsResponse:
    """Bulk archive or unarchive attempts (simulation or benchmark)."""
    try:
        profile_id_str = http_request.state.profile_id
        if not profile_id_str:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )
        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(status_code=400, detail="Session ID is required.")
        profile_id = UUID(profile_id_str)
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_result = await group_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id, id_only=True,
        )
        group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None

        async def _runner(call_id: UUID | None = None) -> ArchiveAttemptsResponse:
            return await archive_attempt_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
                soft=request.soft,
                accept=request.accept,
                idempotency_key=request.idempotency_key,
                call_id=call_id,
            )

        try:
            result = await run_artifact_operation_with_audit(
                pool,
                redis,
                artifact="attempt",
                profile_id=profile_id,
                session_id=session_id,
                group_id=group_id,
                operation="archive",
                arguments={"accept": request.accept} if is_ack else request.model_dump(mode="json"),
                operation_key=request.idempotency_key,  # idempotency replay gate
                response_model=ArchiveAttemptsResponse,
                runner=_runner,
                upload_folder=get_upload_folder(),
            )
        except MissingFilterError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Cache invalidation — HTTP-only concern; not part of the impl contract.
        invalidation_tags = build_attempt_archive_invalidation_tags(
            result.profile_ids_to_invalidate
        )
        await invalidate_tags(invalidation_tags, redis=redis)
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
