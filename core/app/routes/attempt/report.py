"""Get endpoint for reports artifact — bundle response, not paginated.

Renamed from /search; reports returns a multi-section bundle, not a row list.
Use ``/attempt/search`` for paginated attempt history. Routed through the audit
wrapper so ``snapshot_key`` replays a consistent view across related reads.
"""

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.reports.get import get_reports_impl
from app.infra.reports.types import ReportsRequest, ReportsResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter(prefix="/report")


@router.post("", response_model=ReportsResponse)
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
        session_id = getattr(http_request.state, "session_id", None)
        redis = get_redis_client()

        group_id = None
        if session_id:
            group_result = await group_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id, id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> ReportsResponse:
            return await get_reports_impl(
                pool,
                redis,
                profile_id=profile_id,
                request=request,
                bypass_cache=bypass_cache,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="report",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=ReportsResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.snapshot_key,  # read snapshot: replay this view if echoed
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
            operation="artifacts_report",
            request=http_request,
        )
