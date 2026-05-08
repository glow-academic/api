"""Field generations endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.field.generations.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.field.generations import generations_field_impl
from app.infra.field.group import group_field_impl
from app.infra.field.types import (
    GenerationsFieldApiRequest,
    GenerationsFieldApiResponse,
)
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/generations", response_model=GenerationsFieldApiResponse)
async def generations_field(
    request: GenerationsFieldApiRequest,
    http_request: Request,
    response: Response,
) -> GenerationsFieldApiResponse:
    """List field generation groups — composable infra architecture."""
    tags = ["fields"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_field_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> GenerationsFieldApiResponse:
            return await generations_field_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                search=request.search,
                date_from=request.date_from,
                date_to=request.date_to,
                page_limit=request.page_limit,
                page_offset=request.page_offset,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="field",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="generations",
            arguments=request.model_dump(mode="json"),
            response_model=GenerationsFieldApiResponse,
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
            operation="generations_field",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
