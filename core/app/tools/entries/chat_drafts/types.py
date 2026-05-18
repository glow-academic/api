"""Chat drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateChatDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetChatDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    name: str = Field(default="", description="Immutable draft label set at create time")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    document_ids: list[UUID] = Field(..., description="Associated document UUIDs")
    pending_document_ids: list[UUID] = Field(default_factory=list, description="Pending document UUIDs")
    field_ids: list[UUID] = Field(..., description="Associated field UUIDs")
    pending_field_ids: list[UUID] = Field(default_factory=list, description="Pending field UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    image_ids: list[UUID] = Field(..., description="Associated image UUIDs")
    pending_image_ids: list[UUID] = Field(default_factory=list, description="Pending image UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    objective_ids: list[UUID] = Field(..., description="Associated objective UUIDs")
    pending_objective_ids: list[UUID] = Field(default_factory=list, description="Pending objective UUIDs")
    option_ids: list[UUID] = Field(..., description="Associated option UUIDs")
    pending_option_ids: list[UUID] = Field(default_factory=list, description="Pending option UUIDs")
    parameter_field_ids: list[UUID] = Field(..., description="Associated parameter field UUIDs")
    pending_parameter_field_ids: list[UUID] = Field(default_factory=list, description="Pending parameter field UUIDs")
    parameter_ids: list[UUID] = Field(..., description="Associated parameter UUIDs")
    pending_parameter_ids: list[UUID] = Field(default_factory=list, description="Pending parameter UUIDs")
    persona_ids: list[UUID] = Field(..., description="Associated persona UUIDs")
    pending_persona_ids: list[UUID] = Field(default_factory=list, description="Pending persona UUIDs")
    problem_statement_ids: list[UUID] = Field(..., description="Associated problem statement UUIDs")
    pending_problem_statement_ids: list[UUID] = Field(default_factory=list, description="Pending problem statement UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    question_ids: list[UUID] = Field(..., description="Associated question UUIDs")
    pending_question_ids: list[UUID] = Field(default_factory=list, description="Pending question UUIDs")
    scenario_ids: list[UUID] = Field(..., description="Associated scenario UUIDs")
    pending_scenario_ids: list[UUID] = Field(default_factory=list, description="Pending scenario UUIDs")
    video_ids: list[UUID] = Field(..., description="Associated video UUIDs")
    pending_video_ids: list[UUID] = Field(default_factory=list, description="Pending video UUIDs")
