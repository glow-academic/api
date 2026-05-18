"""Rubric artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetRubricsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether rubric was auto-generated")
    mcp: bool = Field(..., description="Whether rubric uses MCP")
    active: bool = Field(..., description="Whether rubric is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    point_ids: list[UUID] | None = Field(None, description="Associated point junction IDs")
    standard_group_ids: list[UUID] | None = Field(None, description="Associated standard group junction IDs")
    standard_ids: list[UUID] | None = Field(None, description="Associated standard junction IDs")
    rubric_ids: list[UUID] | None = Field(None, description="Associated rubric junction IDs")


class CreateRubricResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created rubric")


class UpdateRubricResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated rubric")


class DeleteRubricsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted rubrics")
