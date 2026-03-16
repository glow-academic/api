"""Eval drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateEvalDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetEvalDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    version: int = Field(..., description="Draft version number")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    group_id: UUID = Field(..., description="Generation group UUID")
    session_id: UUID = Field(..., description="Associated session UUID")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    model_ids: list[UUID] = Field(..., description="Associated model UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    rubric_ids: list[UUID] = Field(..., description="Associated rubric UUIDs")
