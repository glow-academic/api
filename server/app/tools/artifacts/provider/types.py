"""Provider artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetProvidersResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether provider was auto-generated")
    mcp: bool = Field(..., description="Whether provider uses MCP")
    active: bool = Field(..., description="Whether provider is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    endpoint_ids: list[UUID] | None = Field(None, description="Associated endpoint junction IDs")
    key_ids: list[UUID] | None = Field(None, description="Associated key junction IDs")
    value_ids: list[UUID] | None = Field(None, description="Associated value junction IDs")
    provider_ids: list[UUID] | None = Field(None, description="Associated provider junction IDs")


class CreateProviderResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created provider")


class UpdateProviderResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated provider")


class DeleteProvidersResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted providers")
