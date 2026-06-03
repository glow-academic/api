"""Benchmark operation event configs (contributed to the ``test`` parent).

Post 19→3 consolidation, benchmark is nested under the ``test`` artifact.
"""

from app.events.types import (
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.benchmark.types import BenchmarkRequest, BenchmarkResponse

BENCHMARK_OPERATION_CONFIGS: dict[str, OperationEventConfig] = {
    "benchmark_get": OperationEventConfig(
        operation="benchmark_get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": BenchmarkRequest,
            "completed": BenchmarkResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"test.benchmark_viewed": None},
    ),
    "benchmark_refresh": OperationEventConfig(
        operation="benchmark_refresh",
        domain_events={"test.benchmark_refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}
