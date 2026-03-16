"""Setting drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSettingDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetSettingDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    version: int = Field(..., description="Draft version number")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    group_id: UUID = Field(..., description="Generation group UUID")
    session_id: UUID = Field(..., description="Associated session UUID")
    agent_ids: list[UUID] = Field(..., description="Associated agent UUIDs")
    auth_item_key_ids: list[UUID] = Field(..., description="Associated auth item key UUIDs")
    auth_ids: list[UUID] = Field(..., description="Associated auth UUIDs")
    color_ids: list[UUID] = Field(..., description="Associated color UUIDs")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    item_ids: list[UUID] = Field(..., description="Associated item UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    provider_key_ids: list[UUID] = Field(..., description="Associated provider key UUIDs")
    threshold_ids: list[UUID] = Field(..., description="Associated threshold UUIDs")
