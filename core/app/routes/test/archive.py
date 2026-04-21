"""Benchmark test archive endpoint."""

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.group.resolve import resolve_group_impl
from app.infra.test.types import ArchiveTestsRequest, ArchiveTestsResponse
from app.tools.entries.calls.create import create_call
from app.tools.entries.runs.create import create_run
from app.tools.entries.test_archive.create import create_test_archive
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
        pool = get_pool()
        redis = get_redis_client()
        # Create group → run → call chain, then archive each test
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id

        group_result = await resolve_group_impl(
            pool, redis,
            artifact_type="test",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )

        async with pool.acquire() as conn:
            run_result = await create_run(
                conn, group_id=group_result.group_id, session_id=session_id
            )
            call_result = await create_call(
                conn, run_id=run_result.id, session_id=session_id
            )

            updated_count = 0
            for test_id in request.test_ids:
                await create_test_archive(
                    conn,
                    test_id=test_id,
                    call_id=call_result.id,
                    archived=request.archived,
                )
                updated_count += 1

        await invalidate_tags(tags, redis=redis)
        response.headers["X-Invalidate-Tags"] = ",".join(tags)

        return ArchiveTestsResponse(updated_count=updated_count)
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="artifacts_test_archive",
            request=http_request,
        )
