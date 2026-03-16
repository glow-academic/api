"""Chat drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateChatDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetChatDraftResponse(BaseModel):
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
    document_ids: list[UUID] = Field(..., description="Associated document UUIDs")
    field_ids: list[UUID] = Field(..., description="Associated field UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    image_ids: list[UUID] = Field(..., description="Associated image UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    objective_ids: list[UUID] = Field(..., description="Associated objective UUIDs")
    option_ids: list[UUID] = Field(..., description="Associated option UUIDs")
    parameter_field_ids: list[UUID] = Field(..., description="Associated parameter field UUIDs")
    parameter_ids: list[UUID] = Field(..., description="Associated parameter UUIDs")
    persona_ids: list[UUID] = Field(..., description="Associated persona UUIDs")
    problem_statement_ids: list[UUID] = Field(..., description="Associated problem statement UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    question_ids: list[UUID] = Field(..., description="Associated question UUIDs")
    scenario_ids: list[UUID] = Field(..., description="Associated scenario UUIDs")
    video_ids: list[UUID] = Field(..., description="Associated video UUIDs")
