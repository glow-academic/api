"""Benchmark export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.benchmark.export import export_benchmark_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.benchmark.types import ExportBenchmarkApiResponse

router = APIRouter()


@router.post("/export", response_model=ExportBenchmarkApiResponse)
async def export_benchmark(
    http_request: Request,
    response: Response,
) -> ExportBenchmarkApiResponse:
    """Export all benchmark data as a clean, denormalized ZIP."""
    profile_id = http_request.state.profile_id
    pool = get_pool()

    return await export_benchmark_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
    )
