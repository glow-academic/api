"""Regression tests for public event naming contracts."""

from __future__ import annotations

from app.events.types import build_default_lifecycle_event_types
from app.infra.stream.registry import EVENT_REGISTRY


def test_domain_events_do_not_collide_with_lifecycle_events() -> None:
    """Public domain event names must stay distinct from lifecycle names."""
    for artifact, config in EVENT_REGISTRY.items():
        for operation_name, operation in config.operations.items():
            lifecycle_names = set()
            if operation.include_call_lifecycle:
                lifecycle_names = set(
                    build_default_lifecycle_event_types(artifact, operation_name)
                )

            domain_names = set(operation.domain_event_names)
            assert not lifecycle_names & domain_names, (
                f"{artifact}.{operation_name} reuses lifecycle names as domain events: "
                f"{sorted(lifecycle_names & domain_names)}"
            )

