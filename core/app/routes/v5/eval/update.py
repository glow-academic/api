"""Eval update endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.eval.update.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.eval.update import update_eval_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.eval.types import (
    UpdateEvalApiRequest,
    UpdateEvalApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/update", response_model=UpdateEvalApiResponse)
async def update_eval(
    request: UpdateEvalApiRequest,
    http_request: Request,
    response: Response,
) -> UpdateEvalApiResponse:
    """Update evals using composable infra architecture."""
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

        async def _runner() -> UpdateEvalApiResponse:
            return await update_eval_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.evals,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="eval",
            profile_id=profile_id,
            session_id=session_id,
            operation="update",
            arguments={
                "evals": [item.model_dump(mode="json") for item in request.evals]
            },
            response_model=UpdateEvalApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "evals"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="update_eval",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
