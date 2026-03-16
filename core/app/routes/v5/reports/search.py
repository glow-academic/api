"""Search endpoint for reports artifact — thin HTTP adapter over the canonical shared operation."""

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.reports.get import get_reports_impl
from app.infra.reports.types import ReportsRequest, ReportsResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/search", response_model=ReportsResponse)
async def get_reports(
    request: ReportsRequest,
    http_request: Request,
    response: Response,
) -> ReportsResponse:
    """Get reports artifact data via composable context resolver."""
    tags = ["artifacts", "reports", "views", "analytics"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

    try:
        pool = get_pool()
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        redis = get_redis_client()
        result = await get_reports_impl(
            pool,
            redis,
            profile_id=profile_id,
            request=request,
            bypass_cache=bypass_cache,
        )
        response.headers["X-Cache-Tags"] = ",".join(tags)
        return result

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="artifacts_reports_get",
            request=http_request,
        )
