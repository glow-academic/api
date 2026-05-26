"""Setting duplicate endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.setting.duplicate.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.setting.duplicate import duplicate_setting_impl
from app.infra.setting.group import group_setting_impl
from app.infra.setting.types import (
    DuplicateSettingApiRequest,
    DuplicateSettingApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post(
    "/duplicate",
    response_model=DuplicateSettingApiResponse,
)
async def duplicate_setting(
    request: DuplicateSettingApiRequest,
    http_request: Request,
    response: Response,
) -> DuplicateSettingApiResponse:
    """Duplicate a setting — composable infra architecture."""
    tags = ["settings"]

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
            group_result = await group_setting_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None
        premint_call_id = None if is_ack else request.idempotency_key

        async def _runner() -> DuplicateSettingApiResponse:
            return await duplicate_setting_impl(
                pool,
                redis,
                profile_id=profile_id,
                id=request.setting_id,
                session_id=session_id,
                accept=request.accept,
                idempotency_key=request.idempotency_key,
                soft=request.soft,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="setting",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="duplicate",
            arguments=request.model_dump(mode="json"),
            response_model=DuplicateSettingApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.idempotency_key,  # idempotency replay gate
            call_id=premint_call_id,  # pre-mint calls_entry with client key (HTTP soft FK)
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="duplicate_setting",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
