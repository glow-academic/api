"""POST /test/archive — thin HTTP adapter over archive_test_impl."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.test.archive import archive_test_impl
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
        result = await archive_test_impl(
            get_pool(),
            get_redis_client(),
            profile_id=http_request.state.profile_id,
            session_id=http_request.state.session_id,
            request=request,
        )
        await invalidate_tags(tags, redis=get_redis_client())
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
