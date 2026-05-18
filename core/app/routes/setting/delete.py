"""Setting delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.setting.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.setting.delete import delete_setting_impl
from app.infra.setting.group import group_setting_impl
from app.infra.setting.types import (
    DeleteSettingApiRequest,
    DeleteSettingApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteSettingApiResponse)
async def delete_setting(
    request: DeleteSettingApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteSettingApiResponse:
    """Bulk delete settings — composable infra architecture."""
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
            )
            group_id = group_result.group_id

        async def _runner() -> DeleteSettingApiResponse:
            return await delete_setting_impl(
                pool,
                redis,
                profile_id=profile_id,
                ids=request.setting_ids,
                session_id=session_id,
                accept=request.accept if request.idempotency_key else None,
                idempotency_key=request.idempotency_key,
                # All-matching path
                all=bool(request.all),
                excluded_ids=request.excluded_ids,
                search=request.search,
                flag_ids=request.flag_ids,
                provider_ids=request.provider_ids,
                auth_ids=request.auth_ids,
                system_ids=request.system_ids,
                filter_department_ids=request.filter_department_ids,
                flag_search=request.flag_search,
                provider_search=request.provider_search,
                auth_search=request.auth_search,
                system_search=request.system_search,
                department_search=request.department_search,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="setting",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="delete",
            arguments=request.model_dump(mode="json", exclude_none=True),
            response_model=DeleteSettingApiResponse,
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
            operation="delete_setting",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
