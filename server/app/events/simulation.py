"""Simulation event declarations for centralized delivery."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.events.types import (
    ArtifactEventsConfig,
    OperationErrorEvent,
    OperationEventConfig,
    require_authenticated_profile,
)
from app.infra.docs.types import ComposedDocsResponse
from app.infra.simulation.types import (
    CreateSimulationApiRequest,
    CreateSimulationApiResponse,
    DeleteSimulationApiRequest,
    DeleteSimulationApiResponse,
    DuplicateSimulationApiRequest,
    DuplicateSimulationApiResponse,
    ExportSimulationApiRequest,
    ExportSimulationApiResponse,
    GetSimulationApiRequest,
    GetSimulationApiResponse,
    GetSimulationDraftsApiResponse,
    PatchSimulationDraftApiRequest,
    PatchSimulationDraftApiResponse,
    UpdateSimulationApiRequest,
    UpdateSimulationApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _simulation_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve simulation IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("simulation_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("simulation_id")
        ]
    )


def _simulation_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated simulation ID from output."""
    del arguments
    return _uuid_list([output.get("simulation_id")])


def _simulation_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _simulation_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


SIMULATION_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="simulation_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetSimulationApiRequest,
            "completed": GetSimulationApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.simulation.viewed": None},
        resolve_entity_ids=lambda arguments, output: _simulation_request_entity_ids(
            arguments, output, "simulation_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateSimulationApiRequest,
            "completed": CreateSimulationApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.simulation.created": CreateSimulationApiResponse,
        },
        resolve_entity_ids=_simulation_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="simulation_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateSimulationApiRequest,
            "completed": UpdateSimulationApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.simulation.updated": UpdateSimulationApiResponse,
        },
        resolve_entity_ids=_simulation_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="simulation_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteSimulationApiRequest,
            "completed": DeleteSimulationApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.simulation.deleted": DeleteSimulationApiResponse,
        },
        resolve_entity_ids=_simulation_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="simulation_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateSimulationApiRequest,
            "completed": DuplicateSimulationApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.simulation.duplicated": DuplicateSimulationApiResponse,
        },
        resolve_entity_ids=_simulation_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchSimulationDraftApiRequest,
            "completed": PatchSimulationDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.simulation.draft.saved": PatchSimulationDraftApiResponse,
        },
        resolve_entity_ids=_simulation_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.simulation.drafts.viewed": GetSimulationDraftsApiResponse,
        },
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.simulation.search.performed": None},
        include_call_lifecycle=False,
    ),
    "docs": OperationEventConfig(
        operation="docs",
        scope="entity",
        entity_key="entity_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "completed": ComposedDocsResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.simulation.docs.viewed": None},
        resolve_entity_ids=lambda arguments, output: _simulation_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="simulation_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportSimulationApiRequest,
            "completed": ExportSimulationApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.simulation.exported": ExportSimulationApiResponse,
        },
        resolve_entity_ids=lambda arguments, output: _simulation_request_entity_ids(
            arguments, output, "simulation_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.simulation.refreshed": None},
    ),
}

SIMULATION_EVENTS = ArtifactEventsConfig(
    artifact="simulation",
    operations=SIMULATION_EVENT_CONFIGS,
)


def get_simulation_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a simulation operation."""
    return SIMULATION_EVENTS.get_operation(operation)
