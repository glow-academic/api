"""Parameter GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.parameter.get import get_parameter_impl
from app.infra.parameter.types import (
    GetParameterApiRequest,
    GetParameterApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=GetParameterApiResponse)
async def get_parameter(
    request: GetParameterApiRequest,
    http_request: Request,
    response: Response,
) -> GetParameterApiResponse:
    """Get parameter information using the canonical shared parameter operation."""
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

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

        async def _runner() -> GetParameterApiResponse:
            return await get_parameter_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                parameter_id=request.parameter_id,
                draft_id=request.draft_id,
                bypass_cache=bypass_cache,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="parameter",
            profile_id=profile_id,
            session_id=session_id,
            draft_id=request.draft_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetParameterApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Cache-Tags"] = "parameters"
        response.headers["X-Cache-Hit"] = "0"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_parameter",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
