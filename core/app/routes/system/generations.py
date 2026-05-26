"""System generations endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.system.generations.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.system.generations import generations_system_impl
from app.infra.system.group import group_system_impl
from app.infra.system.types import (
    GenerationsSystemApiRequest,
    GenerationsSystemApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/generations", response_model=GenerationsSystemApiResponse)
async def generations_system(
    request: GenerationsSystemApiRequest,
    http_request: Request,
    response: Response,
) -> GenerationsSystemApiResponse:
    """List system generation groups — composable infra architecture."""
    tags = ["system"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(status_code=401, detail="Profile ID is required. Please sign in again.")

        session_id = http_request.state.session_id
        pool = get_pool()
        redis = get_redis_client()

        group_id = None
        if session_id:
            group_result = await group_system_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> GenerationsSystemApiResponse:
            return await generations_system_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                search=request.search, date_from=request.date_from, date_to=request.date_to,
                page_limit=request.page_limit, page_offset=request.page_offset,
            )

        result = await run_artifact_operation_with_audit(
            pool, redis, artifact="system", profile_id=profile_id, session_id=session_id,
            group_id=group_id, operation="generations", arguments=request.model_dump(mode="json"),
            response_model=GenerationsSystemApiResponse, runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.snapshot_key,  # read snapshot
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(error=e, route_path=http_request.url.path, operation="generations_system",
                          sql_query=None, sql_params=None, request=http_request)
