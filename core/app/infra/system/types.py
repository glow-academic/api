"""System artifact types — request/response models for system operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# =============================================================================
# Generations Types
# =============================================================================


class GenerationsSystemApiRequest(BaseModel):
    """Request model for system generations endpoint."""
    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsSystemListItem(BaseModel):
    """Single generation group in the system generations response."""
    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsSystemApiResponse(BaseModel):
    """Response model for system generations endpoint."""
    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsSystemListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemSystemApiRequest(BaseModel):
    """Request model for system problem endpoint."""
    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")


class ProblemSystemApiResponse(BaseModel):
    """Response model for system problem endpoint."""
    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")


# =============================================================================
# Export Types — view-aware artifact-level export
# =============================================================================


class ExportSystemApiRequest(BaseModel):
    """Request model for view-aware system export.

    Views: ``activity`` | ``pricing`` | ``group`` | ``session`` | ``health``.
    All views return canonical ``{file_id, file_name, row_count}``; client
    downloads via ``/api/system/download/{file_id}``.
    """

    view: str = Field(
        ...,
        description="View discriminator: 'activity' | 'pricing' | 'group' | 'session' | 'health'",
    )
    session_id: UUID | None = Field(None, description="Target session UUID (required for view='session')")
    group_id: UUID | None = Field(None, description="Target group UUID (required for view='group')")


class ExportSystemApiResponse(BaseModel):
    """Response model for system export — canonical file modality."""

    file_id: UUID = Field(..., description="UUID of the files_resource holding the export bytes")
    file_name: str = Field(..., description="Suggested download file name")
    row_count: int = Field(..., description="Number of data rows in the export")
