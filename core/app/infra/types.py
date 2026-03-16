"""Shared types for the infra layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ResourcePair:
    """Selected (current) + suggestions (available options) for one resource."""

    selected: list
    suggestions: list


@dataclass(frozen=True)
class ArtifactContext:
    """Canonical resolved artifact context returned by every artifact resolver.

    All artifact resolvers (persona, scenario, etc.) return this type.
    Resources are keyed by name ("names", "descriptions", etc.) with ResourcePair values.
    Entries carry artifact-specific non-resource data (draft info, computed flags, catalogs).
    """

    artifact_id: UUID | None
    active: bool
    group_id: UUID
    draft_version: int | None
    resources: dict[str, ResourcePair]
    entries: dict[str, Any]


@dataclass(frozen=True)
class ArtifactRequest:
    """Input descriptor for a single artifact to resolve in websocket context."""

    artifact_type: str  # "persona", "scenario", etc.
    artifact_id: UUID | None
    group_id: UUID
    draft_id: UUID | None = None
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ArtifactWebsocketContext:
    """Flattened artifact context for websocket consumption.

    Resources are prefixed: "get.names" (selected), "search.names" (suggestions).
    Entries are prefixed: "get.draft_persona", "get.runs".
    """

    params: dict
    resources: dict[str, list]
    entries: dict[str, Any]


@dataclass(frozen=True)
class WebsocketContext:
    """Full resolved websocket context across all artifacts."""

    artifacts: dict[str, ArtifactWebsocketContext]
    scores: Any  # ArtifactToolScores — resource → best tool picks
    systems: list
    agents: list
    models: list
    providers: list
    tools: list
    args: list
    args_outputs: list
    prompts: list
    instructions: list
    rubrics: list
