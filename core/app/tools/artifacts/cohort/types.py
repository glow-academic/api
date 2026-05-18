"""Cohort artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetCohortsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether cohort was auto-generated")
    mcp: bool = Field(..., description="Whether cohort uses MCP")
    active: bool = Field(..., description="Whether cohort is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    profiles_ids: list[UUID] | None = Field(None, description="Associated profile junction IDs")
    profile_persona_ids: list[UUID] | None = Field(None, description="Associated profile persona junction IDs")
    simulation_ids: list[UUID] | None = Field(None, description="Associated simulation junction IDs")
    simulation_availability_ids: list[UUID] | None = Field(None, description="Associated simulation availability IDs")
    simulation_position_ids: list[UUID] | None = Field(None, description="Associated simulation position IDs")
    cohort_ids: list[UUID] | None = Field(None, description="Associated cohort junction IDs")


class CreateCohortResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created cohort")


class UpdateCohortResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated cohort")


class DeleteCohortsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted cohorts")
