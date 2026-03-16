"""Types for group artifact endpoints."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.runs_context import RunsContext
from app.tools.entries.calls.types import SearchCallResponse
from app.tools.entries.messages.types import SearchMessageResponse
from app.tools.entries.runs.search import RunViewItem


class GroupListItem(BaseModel):
    """Single group in the list response with hydrated metadata."""

    group_id: UUID = Field(..., description="UUID of the group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    profile_id: UUID | None = Field(None, description="UUID of the user profile")

    group_name: str | None = Field(None, description="Name of the group")

    first_run_at: datetime | None = Field(None, description="Timestamp of the first run")
    last_run_at: datetime | None = Field(None, description="Timestamp of the last run")

    run_count: int = Field(0, description="Number of runs in the group")
    unique_agents: int = Field(0, description="Number of unique agents used")
    unique_models: int = Field(0, description="Number of unique models used")

    total_input_tokens: int = Field(0, description="Total input tokens consumed")
    total_output_tokens: int = Field(0, description="Total output tokens generated")
    total_tokens: int = Field(0, description="Total tokens used")
    total_cost: Decimal = Field(Decimal("0"), description="Total cost of the group")

    agent_ids: list[UUID] | None = Field(None, description="UUIDs of agents used")
    model_ids: list[UUID] | None = Field(None, description="UUIDs of models used")

    # Hydrated metadata
    profile_name: str | None = Field(None, description="Display name of the user profile")
    agent_names: list[str] | None = Field(None, description="Names of agents used")
    model_names: list[str] | None = Field(None, description="Names of models used")


class GetGroupListRequest(BaseModel):
    """Request for group list endpoint."""

    agent_id: UUID | None = Field(default=None, description="Filter by agent UUID")
    model_id: UUID | None = Field(default=None, description="Filter by model UUID")
    date_from: datetime | None = Field(default=None, description="Start date filter")
    date_to: datetime | None = Field(default=None, description="End date filter")

    sort_by: str = Field(
        default="date", description="'date' | 'cost' | 'tokens' | 'runs'"
    )
    sort_order: str = Field(default="desc", description="Sort order: 'asc' or 'desc'")

    page_limit: int = Field(default=50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(default=0, ge=0, description="Offset for pagination")


class GetGroupListResponse(BaseModel):
    """Response for group list endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GroupListItem] = Field(default_factory=list, description="Group list items")
    total_count: int = Field(default=0, description="Total number of matching groups")


# ---- Group Detail types ----


class GroupDetailCallItem(BaseModel):
    """A tool/function call made during the run."""

    id: UUID = Field(..., description="UUID of the call")
    template_name: str | None = Field(None, description="Name of the call template")
    file_path: str | None = Field(None, description="File path associated with the call")
    created_at: datetime = Field(..., description="Timestamp when the call was made")


class GroupDetailMessageItem(BaseModel):
    """A message with upload IDs by media type."""

    id: UUID | None = Field(None, description="UUID of the message")
    role: str | None = Field(None, description="Role of the message sender")
    text_upload_ids: list[UUID] = Field(default_factory=list, description="Text upload UUIDs")
    audio_upload_ids: list[UUID] = Field(default_factory=list, description="Audio upload UUIDs")
    image_upload_ids: list[UUID] = Field(default_factory=list, description="Image upload UUIDs")
    video_upload_ids: list[UUID] = Field(default_factory=list, description="Video upload UUIDs")
    file_upload_ids: list[UUID] = Field(default_factory=list, description="File upload UUIDs")
    call_upload_ids: list[UUID] = Field(default_factory=list, description="Call upload UUIDs")
    calls: list[GroupDetailCallItem] = Field(default_factory=list, description="Tool calls in this message")


class GroupDetailRunItem(BaseModel):
    """Run metadata for the detail response."""

    id: UUID = Field(..., description="UUID of the run")
    created_at: datetime = Field(..., description="Timestamp when the run was created")
    input_tokens: int = Field(0, description="Number of input tokens consumed")
    output_tokens: int = Field(0, description="Number of output tokens generated")
    cached_input_tokens: int = Field(0, description="Number of cached input tokens")
    cost: float = Field(0, description="Cost of the run")
    model_id: UUID | None = Field(None, description="UUID of the model used")
    agent_id: UUID | None = Field(None, description="UUID of the agent used")
    profile_id: UUID | None = Field(None, description="UUID of the user profile")


class GroupDetailRunWithMessages(BaseModel):
    """A run with its messages and context boundary."""

    run: GroupDetailRunItem = Field(..., description="Run metadata")
    messages: list[GroupDetailMessageItem] = Field(default_factory=list, description="Messages in this run")
    previous_context_start_index: int | None = Field(None, description="Index where previous context starts")


class GroupDetailResourceItem(BaseModel):
    """A named resource (model, agent, or profile)."""

    model_id: UUID | None = Field(None, description="UUID of the model")
    agent_id: UUID | None = Field(None, description="UUID of the agent")
    profile_id: UUID | None = Field(None, description="UUID of the profile")
    name: str | None = Field(None, description="Display name of the resource")


class GetGroupDetailRequest(BaseModel):
    """Request for group detail endpoint."""

    group_id: UUID = Field(..., description="UUID of the group to fetch")
    message_limit: int | None = Field(None, description="Maximum number of messages to return")
    message_offset: int | None = Field(None, description="Offset for message pagination")


class GetGroupDetailResponse(BaseModel):
    """Response for group detail endpoint."""

    group_exists: bool = Field(False, description="Whether the group exists")
    actor_name: str | None = Field(None, description="Display name of the current actor")
    group_name: str | None = Field(None, description="Name of the group")
    total_message_count: int = Field(0, description="Total number of messages in the group")
    runs: list[GroupDetailRunWithMessages] = Field(default_factory=list, description="Runs with their messages")
    models: list[GroupDetailResourceItem] = Field(default_factory=list, description="Models used in the group")
    agents: list[GroupDetailResourceItem] = Field(default_factory=list, description="Agents used in the group")
    profiles: list[GroupDetailResourceItem] = Field(default_factory=list, description="Profiles in the group")


@dataclass
class GroupInternalData:
    """Internal data from core group fetching (cacheable layer)."""

    # Domain entries (from MV search tools)
    group_exists: bool = False
    runs: list[RunViewItem] = field(default_factory=list)
    messages: list[SearchMessageResponse] = field(default_factory=list)
    calls: list[SearchCallResponse] = field(default_factory=list)
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
    group_name: str | None = None
    total_message_count: int = 0
    # Resource maps (from context resolver)
    name_map: dict[UUID, str] = field(default_factory=dict)
    tool_name_map: dict[UUID, str] = field(default_factory=dict)


# =============================================================================
# Export Types
# =============================================================================


class ExportGroupApiResponse(BaseModel):
    """Response model for group export."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Name of the exported file")
    mime_type: str = Field(..., description="MIME type of the exported file")
    row_count: int = Field(..., description="Number of rows in the export")
