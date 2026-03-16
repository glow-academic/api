"""Provider drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateProviderDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetProviderDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    version: int = Field(..., description="Draft version number")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    group_id: UUID = Field(..., description="Generation group UUID")
    session_id: UUID = Field(..., description="Associated session UUID")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    endpoint_ids: list[UUID] = Field(..., description="Associated endpoint UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    key_ids: list[UUID] = Field(..., description="Associated key UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    value_ids: list[UUID] = Field(..., description="Associated value UUIDs")
