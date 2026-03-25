"""Rubric create endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.rubric.create.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.rubric.create import create_rubric_impl
from app.infra.rubric.types import (
    CreateRubricApiRequest,
    CreateRubricApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/create", response_model=CreateRubricApiResponse)
async def create_rubric(
    request: CreateRubricApiRequest,
    http_request: Request,
    response: Response,
) -> CreateRubricApiResponse:
    """Create rubrics using composable infra architecture."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> CreateRubricApiResponse:
            return await create_rubric_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.rubrics,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="rubric",
            profile_id=profile_id,
            session_id=session_id,
            operation="create",
            arguments={
                "rubrics": [item.model_dump(mode="json") for item in request.rubrics]
            },
            response_model=CreateRubricApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "rubrics"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="create_rubric",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
