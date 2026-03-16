"""Simulation artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetSimulationsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether simulation was auto-generated")
    mcp: bool = Field(..., description="Whether simulation uses MCP")
    active: bool = Field(..., description="Whether simulation is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario junction IDs")
    scenario_flag_ids: list[UUID] | None = Field(None, description="Associated scenario flag junction IDs")
    scenario_position_ids: list[UUID] | None = Field(None, description="Associated scenario position junction IDs")
    scenario_rubric_ids: list[UUID] | None = Field(None, description="Associated scenario rubric junction IDs")
    scenario_time_limit_ids: list[UUID] | None = Field(None, description="Associated scenario time limit junction IDs")
    simulation_ids: list[UUID] | None = Field(None, description="Associated simulation junction IDs")


class CreateSimulationResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created simulation")


class UpdateSimulationResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated simulation")


class DeleteSimulationsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted simulations")
