"""Profile artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetProfilesResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether profile was auto-generated")
    mcp: bool = Field(..., description="Whether profile uses MCP")
    active: bool = Field(..., description="Whether profile is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    email_ids: list[UUID] | None = Field(None, description="Associated email junction IDs")
    profile_ids: list[UUID] | None = Field(None, description="Associated profile junction IDs")
    request_limit_ids: list[UUID] | None = Field(None, description="Associated request limit junction IDs")
    role_ids: list[UUID] | None = Field(None, description="Associated role junction IDs")


class CreateProfileResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created profile")


class UpdateProfileResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated profile")


class DeleteProfilesResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted profiles")
