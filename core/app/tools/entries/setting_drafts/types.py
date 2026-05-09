"""Setting drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSettingDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetSettingDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    name: str = Field(default="", description="Immutable draft label set at create time")
    agent_ids: list[UUID] = Field(..., description="Associated agent UUIDs")
    auth_item_key_ids: list[UUID] = Field(..., description="Associated auth item key UUIDs")
    auth_ids: list[UUID] = Field(..., description="Associated auth UUIDs")
    color_ids: list[UUID] = Field(..., description="Associated color UUIDs")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    item_ids: list[UUID] = Field(..., description="Associated item UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    provider_ids: list[UUID] = Field(..., description="Associated provider UUIDs")
    provider_key_ids: list[UUID] = Field(..., description="Associated provider key UUIDs")
    threshold_ids: list[UUID] = Field(..., description="Associated threshold UUIDs")
    mcp_ids: list[UUID] | None = None
    logins_ids: list[UUID] | None = None
    pending_agent_ids: list[UUID] = Field(default_factory=list, description="Pending agent UUIDs")
    pending_auth_item_key_ids: list[UUID] = Field(default_factory=list, description="Pending auth item key UUIDs")
    pending_auth_ids: list[UUID] = Field(default_factory=list, description="Pending auth UUIDs")
    pending_color_ids: list[UUID] = Field(default_factory=list, description="Pending color UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_item_ids: list[UUID] = Field(default_factory=list, description="Pending item UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_provider_ids: list[UUID] = Field(default_factory=list, description="Pending provider UUIDs")
    pending_provider_key_ids: list[UUID] = Field(default_factory=list, description="Pending provider key UUIDs")
    pending_threshold_ids: list[UUID] = Field(default_factory=list, description="Pending threshold UUIDs")
    pending_mcp_ids: list[UUID] | None = None
    pending_logins_ids: list[UUID] | None = None
