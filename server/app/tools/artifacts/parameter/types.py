"""Parameter artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetParametersResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether parameter was auto-generated")
    mcp: bool = Field(..., description="Whether parameter uses MCP")
    active: bool = Field(..., description="Whether parameter is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    field_ids: list[UUID] | None = Field(None, description="Associated field junction IDs")
    parameter_ids: list[UUID] | None = Field(None, description="Associated parameter junction IDs")


class CreateParameterResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created parameter")


class UpdateParameterResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated parameter")


class DeleteParametersResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted parameters")
