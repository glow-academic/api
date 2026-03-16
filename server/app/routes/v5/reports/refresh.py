"""Reports refresh endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.refresh.types import RefreshResponse
from app.infra.reports.refresh import refresh_reports_impl

router = APIRouter()


@router.post("/refresh", response_model=RefreshResponse)
async def reports_refresh(
    http_request: Request,
    response: Response,
) -> RefreshResponse:
    """Refresh reports caches."""
    pool = get_pool()
    redis = get_redis_client()
    profile_id = http_request.state.profile_id

    async def _runner() -> RefreshResponse:
        return await refresh_reports_impl(
            pool,
            redis,
            profile_id=profile_id,
        )

    result = await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="reports",
        profile_id=profile_id,
        session_id=http_request.state.session_id,
        operation="refresh",
        arguments={},
        response_model=RefreshResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
    response.headers["X-Invalidate-Tags"] = ",".join(result.invalidated_tags)
    return result
