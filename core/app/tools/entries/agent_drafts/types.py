"""Agent drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAgentDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetAgentDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
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
    prompt_ids: list[UUID] = Field(default_factory=list, description="Associated prompt UUIDs")
    instruction_ids: list[UUID] = Field(default_factory=list, description="Associated instruction UUIDs")
    agent_ids: list[UUID] = Field(default_factory=list, description="Associated agent snapshot UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_model_ids: list[UUID] = Field(default_factory=list, description="Pending model UUIDs")
    pending_tool_ids: list[UUID] = Field(default_factory=list, description="Pending tool UUIDs")
    pending_reasoning_level_ids: list[UUID] = Field(default_factory=list, description="Pending reasoning level UUIDs")
    pending_temperature_level_ids: list[UUID] = Field(default_factory=list, description="Pending temperature level UUIDs")
    pending_voice_ids: list[UUID] = Field(default_factory=list, description="Pending voice UUIDs")
    pending_quality_ids: list[UUID] = Field(default_factory=list, description="Pending quality UUIDs")
    pending_rubric_ids: list[UUID] = Field(default_factory=list, description="Pending rubric UUIDs")
    pending_prompt_ids: list[UUID] = Field(default_factory=list, description="Pending prompt UUIDs")
    pending_instruction_ids: list[UUID] = Field(default_factory=list, description="Pending instruction UUIDs")
    pending_agent_ids: list[UUID] = Field(default_factory=list, description="Pending agent snapshot UUIDs")
