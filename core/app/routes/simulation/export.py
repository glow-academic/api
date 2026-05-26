"""Simulation export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.simulation.export import export_simulation_impl
from app.infra.simulation.group import group_simulation_impl
from app.infra.simulation.types import (
    ExportSimulationApiRequest,
    ExportSimulationApiResponse,
)

router = APIRouter()


@router.post("/export", response_model=ExportSimulationApiResponse)
async def export_simulations(
    body: ExportSimulationApiRequest,
    http_request: Request,
) -> ExportSimulationApiResponse:
    """Export all simulations as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_simulation_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    is_ack = body.accept is not None and body.idempotency_key is not None

    async def _runner(call_id: UUID | None = None) -> ExportSimulationApiResponse:
        return await export_simulation_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            simulation_id=body.simulation_id,
            soft=body.soft,
            accept=body.accept,
            idempotency_key=body.idempotency_key,
            call_id=call_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="simulation",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments={"accept": body.accept} if is_ack else body.model_dump(mode="json"),
        response_model=ExportSimulationApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=body.idempotency_key,  # idempotency replay gate
    )
