"""Rubric drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateRubricDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetRubricDraftResponse(BaseModel):
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
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    point_ids: list[UUID] = Field(..., description="Associated point UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    standard_group_ids: list[UUID] = Field(..., description="Associated standard group UUIDs")
    standard_ids: list[UUID] = Field(..., description="Associated standard UUIDs")
    pending_department_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated pending department UUIDs",
    )
    pending_description_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated pending description UUIDs",
    )
    pending_flag_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated pending flag UUIDs",
    )
    pending_name_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated pending name UUIDs",
    )
    pending_point_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated pending point UUIDs",
    )
    pending_standard_group_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated pending standard group UUIDs",
    )
    pending_standard_ids: list[UUID] = Field(
        default_factory=list,
        description="Associated pending standard UUIDs",
    )
