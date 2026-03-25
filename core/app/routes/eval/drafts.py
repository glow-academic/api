"""Eval drafts list endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.eval.drafts.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.eval.drafts import list_eval_drafts_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.eval.types import GetEvalDraftsApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/drafts", response_model=GetEvalDraftsApiResponse)
async def get_eval_drafts(
    http_request: Request,
    response: Response,
) -> GetEvalDraftsApiResponse:
    """List eval drafts owned by the current profile."""
    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        async def _runner() -> GetEvalDraftsApiResponse:
            context = await list_eval_drafts_impl(
                pool,
                redis,
                profile_id=UUID(profile_id),
                bypass_cache=bypass_cache,
            )
            return GetEvalDraftsApiResponse(entries=context.entries.get("drafts"))

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="eval",
            profile_id=UUID(profile_id),
            session_id=http_request.state.session_id,
            operation="drafts",
            arguments={},
            bypass_cache=bypass_cache,
            response_model=GetEvalDraftsApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        response.headers["X-Cache-Tags"] = "evals,drafts"
        return result

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_eval_drafts",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
