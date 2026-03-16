"""Field artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetFieldsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether field was auto-generated")
    mcp: bool = Field(..., description="Whether field uses MCP")
    active: bool = Field(..., description="Whether field is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Associated conditional parameter junction IDs")
    field_ids: list[UUID] | None = Field(None, description="Associated field junction IDs")


class CreateFieldResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created field")


class UpdateFieldResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated field")


class DeleteFieldsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted fields")
