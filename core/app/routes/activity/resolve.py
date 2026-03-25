"""Problem resolve endpoint."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error


# Inline request/response schemas
class ResolveProblemRequest(BaseModel):
    problem_id: UUID
    resolved: bool = True


class ResolveProblemResponse(BaseModel):
    problem_id: UUID
    resolved: bool
    updated_at: datetime


router = APIRouter()


@router.post("/resolve", response_model=ResolveProblemResponse)
async def resolve_problem(
    request: ResolveProblemRequest,
    http_request: Request,
    response: Response,
) -> ResolveProblemResponse:
    """Resolve or unresolve a problem entry."""
    tags = ["problems", "views", "activity", "summary"]

    try:
        # Get profile_id from header (set by router-level dependency)
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()

        # Create group → run → call → resolve entry chain
        session_id = http_request.state.session_id
        async with pool.acquire() as conn:
            group_result = await create_group(conn, session_id=session_id)
            run_result = await create_run(
                conn, group_id=group_result.id, session_id=session_id
            )
            call_result = await create_call(
                conn, run_id=run_result.id, session_id=session_id
            )

            await create_resolve(
                conn,
                problem_id=request.problem_id,
                resolved=request.resolved,
                call_id=call_result.id,
            )

        result_data = ResolveProblemResponse(
            problem_id=request.problem_id,
            resolved=request.resolved,
            updated_at=datetime.now(),
        )

        # Invalidate cache after mutation
        await invalidate_tags(tags, redis=get_redis_client())
        response.headers["X-Invalidate-Tags"] = ",".join(tags)

        return result_data
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="resolve_problem",
            request=http_request,
        )
