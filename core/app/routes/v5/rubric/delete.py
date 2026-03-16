"""Rubric delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.rubric.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.rubric.delete import delete_rubric_impl
from app.infra.rubric.types import (
    DeleteRubricApiRequest,
    DeleteRubricApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteRubricApiResponse)
async def delete_rubric(
    request: DeleteRubricApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteRubricApiResponse:
    """Bulk delete rubrics — composable infra architecture."""
    tags = ["rubrics"]

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

        async def _runner() -> DeleteRubricApiResponse:
            return await delete_rubric_impl(
                pool,
                redis,
                profile_id=profile_id,
                rubric_ids=request.rubric_ids,
                session_id=session_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="rubric",
            profile_id=profile_id,
            session_id=session_id,
            operation="delete",
            arguments=request.model_dump(mode="json"),
            response_model=DeleteRubricApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="delete_rubric",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
