"""Department update endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.department.update.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.department.update import update_department_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.department.types import (
    UpdateDepartmentApiRequest,
    UpdateDepartmentApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/update", response_model=UpdateDepartmentApiResponse)
async def update_department(
    request: UpdateDepartmentApiRequest,
    http_request: Request,
    response: Response,
) -> UpdateDepartmentApiResponse:
    """Update departments using composable infra architecture."""
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

        async def _runner() -> UpdateDepartmentApiResponse:
            return await update_department_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.departments,
                session_id=session_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="department",
            profile_id=profile_id,
            session_id=session_id,
            operation="update",
            arguments={
                "departments": [
                    item.model_dump(mode="json") for item in request.departments
                ]
            },
            response_model=UpdateDepartmentApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "departments"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="update_department",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
