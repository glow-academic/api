"""Scenario event declarations for centralized delivery."""

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
from app.infra.scenario.types import (
    CreateScenarioApiRequest,
    CreateScenarioApiResponse,
    DeleteScenarioApiRequest,
    DeleteScenarioApiResponse,
    DuplicateScenarioApiRequest,
    DuplicateScenarioApiResponse,
    ExportScenarioApiRequest,
    ExportScenarioApiResponse,
    GetScenarioApiRequest,
    GetScenarioApiResponse,
    GetScenarioDraftsApiResponse,
    PatchScenarioDraftApiRequest,
    PatchScenarioDraftApiResponse,
    UpdateScenarioApiRequest,
    UpdateScenarioApiResponse,
)


def _uuid_list(values: list[Any] | None) -> list[UUID]:
    """Normalize a list of UUID-like values."""
    return [UUID(str(value)) for value in values or [] if value]


def _scenario_result_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve scenario IDs from bulk create/update/delete outputs."""
    del arguments
    return _uuid_list(
        [
            item.get("scenario_id")
            for item in output.get("results", [])
            if isinstance(item, dict) and item.get("scenario_id")
        ]
    )


def _scenario_duplicate_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve duplicated scenario ID from output."""
    del arguments
    return _uuid_list([output.get("scenario_id")])


def _scenario_request_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
    key: str,
) -> list[UUID]:
    """Resolve a single entity ID from request arguments."""
    del output
    return _uuid_list([arguments.get(key)])


def _scenario_draft_entity_ids(
    arguments: dict[str, Any],
    output: dict[str, Any],
) -> list[UUID]:
    """Resolve draft ID from output first, then request input_draft_id."""
    return _uuid_list([output.get("draft_id"), arguments.get("input_draft_id")])


SCENARIO_EVENT_CONFIGS: dict[str, OperationEventConfig] = {
    "get": OperationEventConfig(
        operation="get",
        scope="entity",
        entity_key="scenario_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": GetScenarioApiRequest,
            "completed": GetScenarioApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.scenario.viewed": None},
        resolve_entity_ids=lambda arguments, output: _scenario_request_entity_ids(
            arguments, output, "scenario_id"
        ),
    ),
    "create": OperationEventConfig(
        operation="create",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": CreateScenarioApiRequest,
            "completed": CreateScenarioApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.scenario.created": CreateScenarioApiResponse},
        resolve_entity_ids=_scenario_result_entity_ids,
    ),
    "update": OperationEventConfig(
        operation="update",
        scope="entity",
        entity_key="scenario_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": UpdateScenarioApiRequest,
            "completed": UpdateScenarioApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.scenario.updated": UpdateScenarioApiResponse},
        resolve_entity_ids=_scenario_result_entity_ids,
    ),
    "delete": OperationEventConfig(
        operation="delete",
        scope="entity",
        entity_key="scenario_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DeleteScenarioApiRequest,
            "completed": DeleteScenarioApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.scenario.deleted": DeleteScenarioApiResponse},
        resolve_entity_ids=_scenario_result_entity_ids,
    ),
    "duplicate": OperationEventConfig(
        operation="duplicate",
        scope="entity",
        entity_key="scenario_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": DuplicateScenarioApiRequest,
            "completed": DuplicateScenarioApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.scenario.duplicated": DuplicateScenarioApiResponse},
        resolve_entity_ids=_scenario_duplicate_entity_ids,
    ),
    "draft": OperationEventConfig(
        operation="draft",
        scope="entity",
        entity_key="draft_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": PatchScenarioDraftApiRequest,
            "completed": PatchScenarioDraftApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={
            "artifacts.scenario.draft.saved": PatchScenarioDraftApiResponse,
        },
        resolve_entity_ids=_scenario_draft_entity_ids,
    ),
    "drafts": OperationEventConfig(
        operation="drafts",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={
            "artifacts.scenario.drafts.viewed": GetScenarioDraftsApiResponse,
        },
        include_call_lifecycle=False,
    ),
    "search": OperationEventConfig(
        operation="search",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.scenario.search.performed": None},
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
        domain_events={"artifacts.scenario.docs.viewed": None},
        resolve_entity_ids=lambda arguments, output: _scenario_request_entity_ids(
            arguments, output, "entity_id"
        ),
    ),
    "export": OperationEventConfig(
        operation="export",
        scope="collection",
        entity_key="scenario_id",
        can_subscribe=require_authenticated_profile,
        lifecycle_models={
            "started": ExportScenarioApiRequest,
            "completed": ExportScenarioApiResponse,
            "failed": OperationErrorEvent,
        },
        domain_events={"artifacts.scenario.exported": ExportScenarioApiResponse},
        resolve_entity_ids=lambda arguments, output: _scenario_request_entity_ids(
            arguments, output, "scenario_id"
        ),
    ),
    "refresh": OperationEventConfig(
        operation="refresh",
        scope="collection",
        entity_key=None,
        can_subscribe=require_authenticated_profile,
        domain_events={"artifacts.scenario.refreshed": None},
    ),
}

SCENARIO_EVENTS = ArtifactEventsConfig(
    artifact="scenario",
    operations=SCENARIO_EVENT_CONFIGS,
)


def get_scenario_event_config(operation: str) -> OperationEventConfig | None:
    """Resolve event policy for a scenario operation."""
    return SCENARIO_EVENTS.get_operation(operation)
