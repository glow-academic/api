"""Scenario CSV parse endpoint — thin HTTP adapter.

Core logic lives in app.infra.scenario.csv.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.scenario.csv import ParseScenarioCsvApiResponse, parse_scenario_csv_impl
from app.infra.scenario.group import group_scenario_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/csv", response_model=ParseScenarioCsvApiResponse)
async def parse_scenario_csv(
    file: UploadFile,
    http_request: Request,
) -> ParseScenarioCsvApiResponse:
    """Parse a CSV file and return mapped items for preview."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_scenario_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        # Read file bytes at route boundary (UploadFile can only be read once)
        file_bytes = await file.read()
        file_name = file.filename or "file.csv"
        content_type = file.content_type or "text/csv"

        async def _runner() -> ParseScenarioCsvApiResponse:
            return await parse_scenario_csv_impl(
                pool,
                session_id=session_id,
                file_bytes=file_bytes,
                file_name=file_name,
                content_type=content_type,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="scenario",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="csv",
            arguments={"filename": file_name},
            response_model=ParseScenarioCsvApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="parse_scenario_csv",
            request=http_request,
        )
