"""Invocation GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.invocation.get import get_invocation_impl
from app.infra.invocation.types import GetSuiteRequest, GetSuiteResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=GetSuiteResponse)
async def invocation_get(
    request: GetSuiteRequest,
    http_request: Request,
) -> GetSuiteResponse:
    """Get hydrated resources for benchmark bundle customization."""
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
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        async def _runner() -> GetSuiteResponse:
            return await get_invocation_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                test_id=request.test_id,
                draft_id=request.draft_id,
                descriptions_search=request.descriptions_search,
                bypass_cache=bypass_cache,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="invocation",
            profile_id=profile_id,
            session_id=session_id,
            draft_id=request.draft_id,
            test_id=request.test_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetSuiteResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="invocation_get",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
