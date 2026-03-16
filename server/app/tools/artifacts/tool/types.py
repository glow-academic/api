"""Tool artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetToolsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether tool was auto-generated")
    mcp: bool = Field(..., description="Whether tool uses MCP")
    active: bool = Field(..., description="Whether tool is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    args_ids: list[UUID] | None = Field(None, description="Associated args junction IDs")
    args_outputs_ids: list[UUID] | None = Field(None, description="Associated args outputs junction IDs")
    arg_positions_ids: list[UUID] | None = Field(None, description="Associated arg positions junction IDs")
    artifact_ids: list[UUID] | None = Field(None, description="Associated artifact junction IDs")
    operation_ids: list[UUID] | None = Field(None, description="Associated operation junction IDs")
    tool_ids: list[UUID] | None = Field(None, description="Associated tool junction IDs")


class CreateToolResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created tool")


class UpdateToolResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated tool")


class DeleteToolsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted tools")
