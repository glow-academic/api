"""Eval duplicate endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.eval.duplicate.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.eval.duplicate import duplicate_eval_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.eval.types import (
    DuplicateEvalApiRequest,
    DuplicateEvalApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post(
    "/duplicate",
    response_model=DuplicateEvalApiResponse,
)
async def duplicate_eval(
    request: DuplicateEvalApiRequest,
    http_request: Request,
    response: Response,
) -> DuplicateEvalApiResponse:
    """Duplicate an eval — composable infra architecture."""
    tags = ["evals"]

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

        async def _runner() -> DuplicateEvalApiResponse:
            return await duplicate_eval_impl(
                pool,
                redis,
                profile_id=profile_id,
                eval_id=request.eval_id,
                session_id=session_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="eval",
            profile_id=profile_id,
            session_id=session_id,
            operation="duplicate",
            arguments=request.model_dump(mode="json"),
            response_model=DuplicateEvalApiResponse,
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
            operation="duplicate_eval",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
