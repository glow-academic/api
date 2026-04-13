"""Scenario drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateScenarioDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetScenarioDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    group_id: UUID = Field(..., description="Generation group UUID")
    session_id: UUID = Field(..., description="Associated session UUID")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    document_ids: list[UUID] = Field(..., description="Associated document UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    image_ids: list[UUID] = Field(..., description="Associated image UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    objective_ids: list[UUID] = Field(..., description="Associated objective UUIDs")
    option_ids: list[UUID] = Field(..., description="Associated option UUIDs")
    parameter_field_ids: list[UUID] = Field(..., description="Associated parameter field UUIDs")
    persona_ids: list[UUID] = Field(..., description="Associated persona UUIDs")
    problem_statement_ids: list[UUID] = Field(..., description="Associated problem statement UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    question_ids: list[UUID] = Field(..., description="Associated question UUIDs")
    video_ids: list[UUID] = Field(..., description="Associated video UUIDs")
    # Pending IDs (connections with active=false, awaiting acceptance)
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_problem_statement_ids: list[UUID] = Field(default_factory=list, description="Pending problem statement UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_persona_ids: list[UUID] = Field(default_factory=list, description="Pending persona UUIDs")
    pending_document_ids: list[UUID] = Field(default_factory=list, description="Pending document UUIDs")
    pending_objective_ids: list[UUID] = Field(default_factory=list, description="Pending objective UUIDs")
    pending_image_ids: list[UUID] = Field(default_factory=list, description="Pending image UUIDs")
    pending_video_ids: list[UUID] = Field(default_factory=list, description="Pending video UUIDs")
    pending_question_ids: list[UUID] = Field(default_factory=list, description="Pending question UUIDs")
    pending_option_ids: list[UUID] = Field(default_factory=list, description="Pending option UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_parameter_field_ids: list[UUID] = Field(default_factory=list, description="Pending parameter field UUIDs")
