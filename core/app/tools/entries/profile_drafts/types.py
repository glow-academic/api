"""Profile drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateProfileDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetProfileDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    name: str = Field(default="", description="Immutable draft label set at create time")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    email_ids: list[UUID] = Field(..., description="Associated email UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    role_ids: list[UUID] = Field(..., description="Associated role UUIDs")
    primary_department_ids: list[UUID] = Field(default_factory=list, description="Associated primary_departments_resource UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_email_ids: list[UUID] = Field(default_factory=list, description="Pending email UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_role_ids: list[UUID] = Field(default_factory=list, description="Pending role UUIDs")
    pending_primary_department_ids: list[UUID] = Field(default_factory=list, description="Pending primary_departments UUIDs")
