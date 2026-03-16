"""Model drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateModelDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetModelDraftResponse(BaseModel):
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
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    modality_ids: list[UUID] = Field(..., description="Associated modality UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    pricing_ids: list[UUID] = Field(..., description="Associated pricing UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    provider_ids: list[UUID] = Field(..., description="Associated provider UUIDs")
    quality_ids: list[UUID] = Field(..., description="Associated quality UUIDs")
    reasoning_level_ids: list[UUID] = Field(..., description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] = Field(..., description="Associated temperature level UUIDs")
    value_ids: list[UUID] = Field(..., description="Associated value UUIDs")
    voice_ids: list[UUID] = Field(..., description="Associated voice UUIDs")
