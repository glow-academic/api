"""Agent artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetAgentsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether agent was auto-generated")
    mcp: bool = Field(..., description="Whether agent uses MCP")
    active: bool = Field(..., description="Whether agent is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    model_ids: list[UUID] | None = Field(None, description="Associated model junction IDs")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Associated reasoning level junction IDs")
    temperature_level_ids: list[UUID] | None = Field(None, description="Associated temperature level junction IDs")
    tool_ids: list[UUID] | None = Field(None, description="Associated tool junction IDs")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice junction IDs")
    quality_ids: list[UUID] | None = Field(None, description="Associated quality junction IDs")
    rubric_ids: list[UUID] | None = Field(None, description="Associated rubric junction IDs")
    agent_ids: list[UUID] | None = Field(None, description="Associated agent junction IDs")


class CreateAgentResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created agent")


class UpdateAgentResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated agent")


class DeleteAgentsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted agents")
