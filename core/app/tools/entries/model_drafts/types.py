"""Model drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateModelDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetModelDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    modality_ids: list[UUID] = Field(..., description="Associated modality UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    pricing_ids: list[UUID] = Field(..., description="Associated pricing UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    provider_ids: list[UUID] = Field(..., description="Associated provider UUIDs")
    quality_ids: list[UUID] = Field(..., description="Associated quality UUIDs")
    reasoning_level_ids: list[UUID] = Field(..., description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] = Field(..., description="Associated temperature level UUIDs")
    value_id: UUID | None = Field(None, description="Associated value UUID")
    voice_ids: list[UUID] = Field(..., description="Associated voice UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_modality_ids: list[UUID] = Field(default_factory=list, description="Pending modality UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_pricing_ids: list[UUID] = Field(default_factory=list, description="Pending pricing UUIDs")
    pending_provider_ids: list[UUID] = Field(default_factory=list, description="Pending provider UUIDs")
    pending_quality_ids: list[UUID] = Field(default_factory=list, description="Pending quality UUIDs")
    pending_reasoning_level_ids: list[UUID] = Field(default_factory=list, description="Pending reasoning level UUIDs")
    pending_temperature_level_ids: list[UUID] = Field(default_factory=list, description="Pending temperature level UUIDs")
    pending_value_ids: list[UUID] = Field(default_factory=list, description="Pending value UUIDs")
    pending_voice_ids: list[UUID] = Field(default_factory=list, description="Pending voice UUIDs")
