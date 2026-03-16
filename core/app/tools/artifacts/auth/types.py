"""Auth artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetAuthsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether auth was auto-generated")
    mcp: bool = Field(..., description="Whether auth uses MCP")
    active: bool = Field(..., description="Whether auth is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    item_ids: list[UUID] | None = Field(None, description="Associated item junction IDs")
    protocol_ids: list[UUID] | None = Field(None, description="Associated protocol junction IDs")
    slug_ids: list[UUID] | None = Field(None, description="Associated slug junction IDs")
    auth_ids: list[UUID] | None = Field(None, description="Associated auth junction IDs")


class CreateAuthResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created auth")


class UpdateAuthResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated auth")


class DeleteAuthsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted auths")
