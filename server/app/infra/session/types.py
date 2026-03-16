"""Types for session artifact endpoints."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.runs_context import RunsContext
from app.tools.entries.runs.search import RunViewItem


class ArtifactSessionGroup(BaseModel):
    """Single group entry for a session."""

    group_id: UUID = Field(..., description="UUID of the group")
    group_name: str | None = Field(None, description="Name of the group")
    first_run_at: datetime | None = Field(None, description="Timestamp of the first run")
    last_run_at: datetime | None = Field(None, description="Timestamp of the last run")
    run_count: int = Field(0, description="Number of runs in the group")
    total_tokens: int = Field(0, description="Total tokens used in the group")
    total_cost: Decimal = Field(Decimal("0"), description="Total cost of the group")


class SessionListItem(BaseModel):
    """Single session in the list response with hydrated metadata."""

    session_id: UUID = Field(..., description="UUID of the session")
    profile_id: UUID | None = Field(None, description="UUID of the user profile")
    profile_name: str | None = Field(None, description="Display name of the user profile")

    session_created_at: datetime | None = Field(None, description="Timestamp when session was created")
    session_updated_at: datetime | None = Field(None, description="Timestamp when session was last updated")

    active: bool = Field(False, description="Whether the session is active")

    group_count: int = Field(0, description="Number of groups in the session")
    run_count: int = Field(0, description="Number of runs in the session")
    first_run_at: datetime | None = Field(None, description="Timestamp of the first run")
    last_run_at: datetime | None = Field(None, description="Timestamp of the last run")

    total_tokens: int = Field(0, description="Total tokens used in the session")
    total_cost: Decimal = Field(Decimal("0"), description="Total cost of the session")

    # Enrichment counts (Phase 1)
    chat_count: int = Field(0, description="Number of chats in the session")
    attempt_count: int = Field(0, description="Number of attempts in the session")
    message_count: int = Field(0, description="Number of messages in the session")
    problem_count: int = Field(0, description="Number of problems in the session")


class GetSessionListRequest(BaseModel):
    """Request for session list endpoint."""

    active: bool | None = Field(default=None, description="Filter by active status")
    date_from: datetime | None = Field(default=None, description="Start date filter")
    date_to: datetime | None = Field(default=None, description="End date filter")
    department_ids: list[str] = Field(default_factory=list, description="Department IDs to filter by")
    roles: list[str] = Field(default_factory=list, description="Roles to filter by")

    sort_by: str = Field(
        default="date", description="'date' | 'cost' | 'tokens' | 'groups' | 'runs'"
    )
    sort_order: str = Field(default="desc", description="Sort order: 'asc' or 'desc'")

    page_limit: int = Field(default=50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(default=0, ge=0, description="Offset for pagination")


class GetSessionListResponse(BaseModel):
    """Response for session list endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[SessionListItem] = Field(default_factory=list, description="Session list items")
    total_count: int = Field(default=0, description="Total number of matching sessions")
    page: int = Field(default=0, description="Current page number")
    page_size: int = Field(default=50, description="Number of items per page")
    total_pages: int = Field(default=0, description="Total number of pages")


class SessionTimelineItem(BaseModel):
    """Single event in the unified session timeline."""

    event_type: str | None = Field(None, description="Type of the timeline event")
    entity_id: UUID | None = Field(None, description="UUID of the related entity")
    entity_name: str | None = Field(None, description="Name of the related entity")
    created_at: datetime | None = Field(None, description="Timestamp when the event occurred")
    extra_1: str | None = Field(None, description="Additional context field 1")
    extra_2: str | None = Field(None, description="Additional context field 2")


class GetSessionDetailRequest(BaseModel):
    """Request for session detail endpoint."""

    session_id: UUID = Field(..., description="UUID of the session to fetch")


class GetSessionDetailResponse(BaseModel):
    """Response for session detail endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    session_exists: bool = Field(False, description="Whether the session exists")
    session_id: UUID | None = Field(None, description="UUID of the session")
    profile_id: UUID | None = Field(None, description="UUID of the user profile")
    profile_name: str | None = Field(None, description="Display name of the user profile")
    session_created_at: datetime | None = Field(None, description="Timestamp when session was created")
    active: bool = Field(False, description="Whether the session is active")
    groups: list[ArtifactSessionGroup] = Field(default_factory=list, description="Groups in the session")
    timeline: list[SessionTimelineItem] = Field(default_factory=list, description="Timeline events for the session")


@dataclass
class SessionInternalData:
    """Internal data from core session fetching (cacheable layer)."""

    # Domain entries (from MV search tools)
    session_exists: bool = False
    session: Any = None
    groups: list = field(default_factory=list)
    runs: list[RunViewItem] = field(default_factory=list)
    # Timeline source entries
    logins: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    chats: list = field(default_factory=list)
    attempt_homes: list = field(default_factory=list)
    practices: list = field(default_factory=list)
    # Config chain (from resource get tools)
    config_agents: list = field(default_factory=list)
    config_models: list = field(default_factory=list)
    config_providers: list = field(default_factory=list)
    config_tools: list = field(default_factory=list)
    config_systems: list = field(default_factory=list)
    config_profile: list = field(default_factory=list)
    runs_today: RunsContext | None = None
    resource_agent_ids: dict[str, UUID | None] = field(default_factory=dict)
    resource_system_ids: dict[str, UUID | None] = field(default_factory=dict)
    group_id: UUID | None = None
    # Context
    actor_name: str | None = None
    profile_name: str | None = None
    # Resource maps
    name_map: dict[UUID, str] = field(default_factory=dict)


# =============================================================================
# Export Types
# =============================================================================


class ExportSessionApiResponse(BaseModel):
    """Response model for session export."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Name of the exported file")
    mime_type: str = Field(..., description="MIME type of the exported file")
    row_count: int = Field(..., description="Number of rows in the export")
