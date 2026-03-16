"""Test GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.test.get import get_test_impl_cached
from app.infra.test.types import (
    GetTestArtifactRequest,
    GetTestArtifactResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=GetTestArtifactResponse)
async def get_test_artifact(
    request: GetTestArtifactRequest,
    http_request: Request,
    response: Response,
) -> GetTestArtifactResponse:
    """Get benchmark test artifact details with tests/invocations in parallel."""
    try:
        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        cache_hit_holder = {"value": False}

        async def _runner() -> GetTestArtifactResponse:
            response_data, cache_hit = await get_test_impl_cached(
                pool=pool,
                test_id=request.test_id,
                bypass_cache=bypass_cache,
                cache_key_path=http_request.url.path,
            )
            cache_hit_holder["value"] = cache_hit
            return response_data

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="test",
            profile_id=http_request.state.profile_id,
            session_id=http_request.state.session_id,
            test_id=request.test_id,
            operation="get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetTestArtifactResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
        cache_hit = cache_hit_holder["value"]

        response.headers["X-Cache-Tags"] = "artifacts,test"
        response.headers["X-Cache-Hit"] = "1" if cache_hit else "0"
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="artifacts_test_get",
            request=http_request,
        )
