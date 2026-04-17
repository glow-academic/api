"""Department drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateDepartmentDraftResponse(BaseModel):
    """Response from the department draft create tool."""

    id: UUID = Field(..., description="UUID of the created draft")


class GetDepartmentDraftResponse(BaseModel):
    """Resolved department draft entry with selected and pending links."""

    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    setting_ids: list[UUID] = Field(..., description="Associated setting UUIDs")
    pending_description_ids: list[UUID] = Field(
        default_factory=list,
        description="Inactive pending description UUIDs",
    )
    pending_flag_ids: list[UUID] = Field(
        default_factory=list,
        description="Inactive pending flag UUIDs",
    )
    pending_name_ids: list[UUID] = Field(
        default_factory=list,
        description="Inactive pending name UUIDs",
    )
    pending_setting_ids: list[UUID] = Field(
        default_factory=list,
        description="Inactive pending setting UUIDs",
    )
