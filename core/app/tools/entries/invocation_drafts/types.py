"""Invocation drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateInvocationDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetInvocationDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    name: str = Field(default="", description="Immutable draft label set at create time")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    key_ids: list[UUID] = Field(..., description="Associated key UUIDs")
    modality_ids: list[UUID] = Field(default_factory=list, description="Associated modality UUIDs")
    quality_ids: list[UUID] = Field(default_factory=list, description="Associated quality UUIDs")
    model_flag_ids: list[UUID] = Field(..., description="Associated model flag UUIDs")
    model_position_ids: list[UUID] = Field(..., description="Associated model position UUIDs")
    model_rubric_ids: list[UUID] = Field(..., description="Associated model rubric UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    reasoning_level_ids: list[UUID] = Field(..., description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] = Field(..., description="Associated temperature level UUIDs")
    voice_ids: list[UUID] = Field(..., description="Associated voice UUIDs")
    value_id: UUID | None = Field(None, description="Associated value UUID")
    pricing_ids: list[UUID] = Field(..., description="Associated pricing UUIDs")
    endpoint_ids: list[UUID] = Field(..., description="Associated endpoint UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_key_ids: list[UUID] = Field(default_factory=list, description="Pending key UUIDs")
    pending_modality_ids: list[UUID] = Field(default_factory=list, description="Pending modality UUIDs")
    pending_quality_ids: list[UUID] = Field(default_factory=list, description="Pending quality UUIDs")
    pending_model_flag_ids: list[UUID] = Field(default_factory=list, description="Pending model flag UUIDs")
    pending_model_position_ids: list[UUID] = Field(default_factory=list, description="Pending model position UUIDs")
    pending_model_rubric_ids: list[UUID] = Field(default_factory=list, description="Pending model rubric UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_reasoning_level_ids: list[UUID] = Field(default_factory=list, description="Pending reasoning level UUIDs")
    pending_temperature_level_ids: list[UUID] = Field(default_factory=list, description="Pending temperature level UUIDs")
    pending_voice_ids: list[UUID] = Field(default_factory=list, description="Pending voice UUIDs")
    pending_value_ids: list[UUID] = Field(default_factory=list, description="Pending value UUIDs")
    pending_pricing_ids: list[UUID] = Field(default_factory=list, description="Pending pricing UUIDs")
    pending_endpoint_ids: list[UUID] = Field(default_factory=list, description="Pending endpoint UUIDs")
