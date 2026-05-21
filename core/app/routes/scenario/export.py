"""Scenario export endpoint — thin HTTP adapter.

Core logic lives in app.infra.scenario.export.
"""

from fastapi import APIRouter, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.scenario.export import export_scenario_impl
from app.infra.scenario.group import group_scenario_impl
from app.infra.scenario.types import (
    ExportScenarioApiRequest,
    ExportScenarioApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/export", response_model=ExportScenarioApiResponse)
async def export_scenarios(
    body: ExportScenarioApiRequest,
    http_request: Request,
) -> ExportScenarioApiResponse:
    """Export all scenarios as a clean, denormalized CSV."""
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
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> ExportScenarioApiResponse:
            return await export_scenario_impl(
                pool,
                redis,
                profile_id=profile_id,
                scenario_id=body.scenario_id,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="scenario",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="export",
            arguments=body.model_dump(mode="json"),
            response_model=ExportScenarioApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="export_scenario",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
