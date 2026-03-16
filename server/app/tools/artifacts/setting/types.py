"""Setting artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetSettingsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether setting was auto-generated")
    mcp: bool = Field(..., description="Whether setting uses MCP")
    active: bool = Field(..., description="Whether setting is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    color_ids: list[UUID] | None = Field(None, description="Associated color junction IDs")
    profile_ids: list[UUID] | None = Field(None, description="Associated profile junction IDs")
    auth_item_keys_ids: list[UUID] | None = Field(None, description="Associated auth item keys junction IDs")
    provider_key_ids: list[UUID] | None = Field(None, description="Associated provider key junction IDs")
    threshold_ids: list[UUID] | None = Field(None, description="Associated threshold junction IDs")
    systems_ids: list[UUID] | None = Field(None, description="Associated systems junction IDs")
    setting_ids: list[UUID] | None = Field(None, description="Associated setting junction IDs")
    auth_ids: list[UUID] | None = Field(None, description="Associated auth junction IDs")
    auth_item_value_ids: list[UUID] | None = Field(None, description="Associated auth item value junction IDs")


class CreateSettingResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created setting")


class UpdateSettingResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated setting")


class DeleteSettingsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted settings")
