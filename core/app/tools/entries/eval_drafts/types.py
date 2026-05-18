"""Eval drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateEvalDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetEvalDraftResponse(BaseModel):
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
    model_ids: list[UUID] = Field(..., description="Associated model UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    rubric_ids: list[UUID] = Field(..., description="Associated rubric UUIDs")
    model_flag_ids: list[UUID] = Field(default_factory=list, description="Associated model flag UUIDs")
    model_position_ids: list[UUID] = Field(default_factory=list, description="Associated model position UUIDs")
    model_rubric_ids: list[UUID] = Field(default_factory=list, description="Associated model rubric UUIDs")
    pending_department_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated department UUIDs stored as inactive pending links",
    )
    pending_description_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated description UUIDs stored as inactive pending links",
    )
    pending_flag_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated flag UUIDs stored as inactive pending links",
    )
    pending_model_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated model UUIDs stored as inactive pending links",
    )
    pending_name_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated name UUIDs stored as inactive pending links",
    )
    pending_rubric_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated rubric UUIDs stored as inactive pending links",
    )
    pending_model_flag_ids: list[UUID] = Field(
        default_factory=list,
        description="Pending model flag UUIDs",
    )
    pending_model_position_ids: list[UUID] = Field(
        default_factory=list,
        description="Pending model position UUIDs",
    )
    pending_model_rubric_ids: list[UUID] = Field(
        default_factory=list,
        description="Pending model rubric UUIDs",
    )
