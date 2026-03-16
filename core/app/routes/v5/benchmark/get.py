"""Get endpoint for benchmark artifact — thin HTTP adapter over the canonical shared operation."""

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.benchmark.get import get_benchmark_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.benchmark.types import BenchmarkRequest, BenchmarkResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=BenchmarkResponse)
async def get_benchmark(
    request: BenchmarkRequest,
    http_request: Request,
    response: Response,
) -> BenchmarkResponse:
    """Get benchmark artifact data with the canonical shared benchmark operation."""
    tags = ["artifacts", "benchmark"]
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

        async def _runner() -> BenchmarkResponse:
            return await get_benchmark_impl(
                pool,
                redis,
                profile_id=profile_id,
                request=request,
                bypass_cache=bypass_cache,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="benchmark",
            profile_id=profile_id,
            session_id=session_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=BenchmarkResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
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
            operation="artifacts_benchmark_get",
            request=http_request,
        )
