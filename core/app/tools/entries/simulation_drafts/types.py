"""Simulation drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateSimulationDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetSimulationDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    scenario_flag_ids: list[UUID] = Field(..., description="Associated scenario flag UUIDs")
    scenario_position_ids: list[UUID] = Field(..., description="Associated scenario position UUIDs")
    scenario_rubric_ids: list[UUID] = Field(..., description="Associated scenario rubric UUIDs")
    scenario_time_limit_ids: list[UUID] = Field(..., description="Associated scenario time limit UUIDs")
    scenario_ids: list[UUID] = Field(..., description="Associated scenario UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_scenario_flag_ids: list[UUID] = Field(default_factory=list, description="Pending scenario flag UUIDs")
    pending_scenario_position_ids: list[UUID] = Field(default_factory=list, description="Pending scenario position UUIDs")
    pending_scenario_rubric_ids: list[UUID] = Field(default_factory=list, description="Pending scenario rubric UUIDs")
    pending_scenario_time_limit_ids: list[UUID] = Field(default_factory=list, description="Pending scenario time limit UUIDs")
    pending_scenario_ids: list[UUID] = Field(default_factory=list, description="Pending scenario UUIDs")
