"""Department artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetDepartmentsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether department was auto-generated")
    mcp: bool = Field(..., description="Whether department uses MCP")
    active: bool = Field(..., description="Whether department is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    settings_ids: list[UUID] | None = Field(None, description="Associated settings junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")


class CreateDepartmentResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created department")


class UpdateDepartmentResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated department")


class DeleteDepartmentsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted departments")
