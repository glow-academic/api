"""Agent drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAgentDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetAgentDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    version: int = Field(..., description="Draft version number")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    group_id: UUID = Field(..., description="Generation group UUID")
    session_id: UUID = Field(..., description="Associated session UUID")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    model_ids: list[UUID] = Field(..., description="Associated model UUIDs")
    tool_ids: list[UUID] = Field(..., description="Associated tool UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    reasoning_level_ids: list[UUID] = Field(..., description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] = Field(..., description="Associated temperature level UUIDs")
    voice_ids: list[UUID] = Field(..., description="Associated voice UUIDs")
    quality_ids: list[UUID] = Field(..., description="Associated quality UUIDs")
    rubric_ids: list[UUID] = Field([], description="Associated rubric UUIDs")
