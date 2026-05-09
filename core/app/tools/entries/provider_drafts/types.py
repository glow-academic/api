"""Provider drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateProviderDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetProviderDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    name: str = Field(default="", description="Immutable draft label set at create time")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    endpoint_ids: list[UUID] = Field(..., description="Associated endpoint UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    key_ids: list[UUID] = Field(..., description="Associated key UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    value_id: UUID | None = Field(None, description="Associated value UUID")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_endpoint_ids: list[UUID] = Field(default_factory=list, description="Pending endpoint UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_key_ids: list[UUID] = Field(default_factory=list, description="Pending key UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_value_ids: list[UUID] = Field(default_factory=list, description="Pending value UUIDs")
