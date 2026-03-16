"""Persona drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreatePersonaDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetPersonaDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    version: int = Field(..., description="Draft version number")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    group_id: UUID = Field(..., description="Generation group UUID")
    session_id: UUID = Field(..., description="Associated session UUID")
    color_ids: list[UUID] = Field(..., description="Associated color UUIDs")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    example_ids: list[UUID] = Field(..., description="Associated example UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    icon_ids: list[UUID] = Field(..., description="Associated icon UUIDs")
    instruction_ids: list[UUID] = Field(..., description="Associated instruction UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    parameter_field_ids: list[UUID] = Field(..., description="Associated parameter field UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    voice_ids: list[UUID] = Field(..., description="Associated voice UUIDs")
