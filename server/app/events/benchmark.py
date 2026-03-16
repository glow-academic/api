"""Benchmark event declarations for centralized delivery."""

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.benchmark.types import BenchmarkRequest, BenchmarkResponse

BENCHMARK_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": BenchmarkRequest,
            "completed": BenchmarkResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.benchmark.viewed": None},
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        domain_events={"artifacts.benchmark.refreshed": None},
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
    ),
}

BENCHMARK_EVENTS = ArtifactEventsConfig(
    artifact="benchmark",
    operations=BENCHMARK_EVENT_CONFIGS,
)


def get_benchmark_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a benchmark operation."""
    return BENCHMARK_EVENTS.get_operation(operation)
