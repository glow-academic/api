"""Eval delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.eval.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.eval.delete import delete_eval_impl
from app.infra.eval.group import group_eval_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.eval.types import (
    DeleteEvalApiRequest,
    DeleteEvalApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteEvalApiResponse)
async def delete_eval(
    request: DeleteEvalApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteEvalApiResponse:
    """Bulk delete evals — composable infra architecture."""
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

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_eval_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> DeleteEvalApiResponse:
            return await delete_eval_impl(
                pool,
                redis,
                profile_id=profile_id,
                eval_ids=request.eval_ids,
                session_id=session_id,
                accept=request.accept,
                idempotency_key=request.idempotency_key,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="eval",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="delete",
            arguments=request.model_dump(mode="json"),
            response_model=DeleteEvalApiResponse,
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
            operation="delete_eval",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
