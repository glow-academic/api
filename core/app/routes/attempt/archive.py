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
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
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
        invalidation_tags = ["attempts", "dashboard"]
        for pid in result.profile_ids_to_invalidate or []:
            invalidation_tags.extend([
                f"home:profile:{pid}",
                f"reports:profile:{pid}",
                f"practice:profile:{pid}",
                f"history:profile:{pid}",
            ])
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
