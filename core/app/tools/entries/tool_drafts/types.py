"""Tool drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateToolDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetToolDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    arg_position_ids: list[UUID] = Field(..., description="Associated arg position UUIDs")
    arg_ids: list[UUID] = Field(..., description="Associated arg UUIDs")
    args_output_ids: list[UUID] = Field(..., description="Associated args output UUIDs")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    instruction_ids: list[UUID] = Field(default_factory=list, description="Associated instruction UUIDs")
    permission_ids: list[UUID] = Field(..., description="Associated permission UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    agent_ids: list[UUID] = Field(default_factory=list, description="Associated agent UUIDs")
    pending_arg_position_ids: list[UUID] = Field(default_factory=list, description="Pending arg position UUIDs")
    pending_arg_ids: list[UUID] = Field(default_factory=list, description="Pending arg UUIDs")
    pending_args_output_ids: list[UUID] = Field(default_factory=list, description="Pending args output UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_instruction_ids: list[UUID] = Field(default_factory=list, description="Pending instruction UUIDs")
    pending_permission_ids: list[UUID] = Field(default_factory=list, description="Pending permission UUIDs")
    pending_agent_ids: list[UUID] = Field(default_factory=list, description="Pending agent UUIDs")
