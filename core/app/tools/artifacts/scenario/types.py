"""Scenario artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetScenariosResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether scenario was auto-generated")
    mcp: bool = Field(..., description="Whether scenario uses MCP")
    active: bool = Field(..., description="Whether scenario is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    document_ids: list[UUID] | None = Field(None, description="Associated document junction IDs")
    image_ids: list[UUID] | None = Field(None, description="Associated image junction IDs")
    objective_ids: list[UUID] | None = Field(None, description="Associated objective junction IDs")
    option_ids: list[UUID] | None = Field(None, description="Associated option junction IDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Associated parameter field junction IDs")
    persona_ids: list[UUID] | None = Field(None, description="Associated persona junction IDs")
    problem_statement_ids: list[UUID] | None = Field(None, description="Associated problem statement junction IDs")
    question_ids: list[UUID] | None = Field(None, description="Associated question junction IDs")
    video_ids: list[UUID] | None = Field(None, description="Associated video junction IDs")
    scenario_ids: list[UUID] | None = Field(None, description="Associated scenario junction IDs")


class CreateScenarioResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created scenario")


class UpdateScenarioResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated scenario")


class DeleteScenariosResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted scenarios")
