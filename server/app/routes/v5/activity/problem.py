"""Problem create endpoint."""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.create import create_group
from app.tools.entries.problems.create import (
    create_problem as create_problem_entry,
)
from app.tools.entries.runs.create import create_run
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error


# Inline request/response schemas
class CreateProblemRequest(BaseModel):
    type: str
    message: str


class CreateProblemResponse(BaseModel):
    problem_id: str  # UUID
    success: bool
    message: str


router = APIRouter()


@router.post("/problem", response_model=CreateProblemResponse)
async def create_problem(
    request: CreateProblemRequest,
    http_request: Request,
    response: Response,
) -> CreateProblemResponse:
    """Create new problem entry."""
    tags = ["problems", "views", "activity"]

    try:
        # Validate problem type
        valid_types = ["feature", "bug", "question", "other"]
        if request.type not in valid_types:
            raise HTTPException(
                status_code=400, detail=f"Invalid problem type: {request.type}"
            )

        # Validate message
        if not request.message or not request.message.strip():
            raise HTTPException(status_code=400, detail="Message is required")

        if len(request.message) > 1000:
            raise HTTPException(
                status_code=400, detail="Message must be less than 1000 characters"
            )

        # Get profile_id from header (set by router-level dependency)
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()
        identity = await resolve_profile_identity_context(pool, profile_id, redis)
        if identity is None:
            raise HTTPException(
                status_code=401,
                detail="Profile not found. Please sign in again.",
            )

        # Create group → run → call → problem entry chain
        session_id = http_request.state.session_id
        async with pool.acquire() as conn:
            group_result = await create_group(conn, session_id=session_id)
            run_result = await create_run(
                conn, group_id=group_result.id, session_id=session_id
            )
            call_result = await create_call(
                conn, run_id=run_result.id, session_id=session_id
            )

            problem_result = await create_problem_entry(
                conn,
                session_id=session_id,
                call_id=call_result.id,
                type=request.type,
                message=request.message,
                profile_id=identity.profiles_id,
            )

        result_data = CreateProblemResponse(
            problem_id=str(problem_result.id),
            success=True,
            message="Problem created successfully",
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
            operation="create_problem",
            request=http_request,
        )
