"""POST /test/archive — routed through the audit wrapper (idempotency + soft/accept)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.test.archive import archive_test_impl
from app.infra.test.group import group_test_impl
from app.infra.test.types import ArchiveTestsRequest, ArchiveTestsResponse
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/archive", response_model=ArchiveTestsResponse)
async def archive_test_artifacts(
    request: ArchiveTestsRequest,
    http_request: Request,
    response: Response,
) -> ArchiveTestsResponse:
    """Archive or unarchive benchmark tests by IDs."""
    tags = ["benchmark", "test", "artifacts"]
    try:
        profile_id = UUID(str(http_request.state.profile_id))
        session_id = http_request.state.session_id
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking.
        group_id = None
        if session_id:
            group_result = await group_test_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None

        async def _runner(call_id: UUID | None = None) -> ArchiveTestsResponse:
            return await archive_test_impl(
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

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="test",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="archive",
            arguments={"accept": request.accept} if is_ack else request.model_dump(mode="json"),
            operation_key=request.idempotency_key,  # idempotency replay gate
            response_model=ArchiveTestsResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        await invalidate_tags(tags, redis=redis)
        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="artifacts_test_archive",
            request=http_request,
        )
