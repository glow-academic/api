"""Department export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.department.export import export_department_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.department.types import ExportDepartmentApiRequest, ExportDepartmentApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportDepartmentApiResponse)
async def export_departments(
    body: ExportDepartmentApiRequest,
    http_request: Request,
) -> ExportDepartmentApiResponse:
    """Export all departments as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_department_impl(
        pool,
        redis,
        profile_id=profile_id,
        department_id=body.department_id,
    )
