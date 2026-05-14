"""Types for group artifact endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


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
    """Request for group list/search endpoint."""

    search: str | None = Field(default=None, description="Name search (ILIKE)")
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


# =============================================================================
# Export Types
# =============================================================================


class ExportGroupApiResponse(BaseModel):
    """Response model for group export."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Name of the exported file")
    mime_type: str = Field(..., description="MIME type of the exported file")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsGroupApiRequest(BaseModel):
    """Request model for group generations endpoint."""

    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsGroupListItem(BaseModel):
    """Single generation group in the group generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsGroupApiResponse(BaseModel):
    """Response model for group generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsGroupListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemGroupApiRequest(BaseModel):
    """Request model for group problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool = Field(True, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemGroupApiResponse(BaseModel):
    """Response model for group problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
