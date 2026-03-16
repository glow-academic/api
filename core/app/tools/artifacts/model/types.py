"""Model artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetModelsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether model was auto-generated")
    mcp: bool = Field(..., description="Whether model uses MCP")
    active: bool = Field(..., description="Whether model is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    modality_ids: list[UUID] | None = Field(None, description="Associated modality junction IDs")
    pricing_ids: list[UUID] | None = Field(None, description="Associated pricing junction IDs")
    provider_ids: list[UUID] | None = Field(None, description="Associated provider junction IDs")
    quality_ids: list[UUID] | None = Field(None, description="Associated quality junction IDs")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Associated reasoning level junction IDs")
    temperature_level_ids: list[UUID] | None = Field(None, description="Associated temperature level junction IDs")
    value_ids: list[UUID] | None = Field(None, description="Associated value junction IDs")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice junction IDs")
    model_ids: list[UUID] | None = Field(None, description="Associated model junction IDs")


class CreateModelResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created model")


class UpdateModelResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated model")


class DeleteModelsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted models")
