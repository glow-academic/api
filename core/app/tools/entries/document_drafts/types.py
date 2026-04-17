"""Document drafts entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateDocumentDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the created draft")


class GetDocumentDraftResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the draft")
    created_at: datetime = Field(..., description="Creation timestamp")
    generated: bool = Field(..., description="Whether this was AI-generated")
    mcp: bool = Field(..., description="Whether MCP tooling was used")
    active: bool = Field(..., description="Whether this draft is active")
    session_id: UUID = Field(..., description="Associated session UUID")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    description_ids: list[UUID] = Field(..., description="Associated description UUIDs")
    file_ids: list[UUID] = Field(..., description="Associated file UUIDs")
    flag_ids: list[UUID] = Field(..., description="Associated flag UUIDs")
    image_ids: list[UUID] = Field(..., description="Associated image UUIDs")
    name_ids: list[UUID] = Field(..., description="Associated name UUIDs")
    parameter_field_ids: list[UUID] = Field(..., description="Associated parameter field UUIDs")
    parameter_ids: list[UUID] = Field(..., description="Associated parameter UUIDs")
    profile_ids: list[UUID] = Field(..., description="Associated profile UUIDs")
    text_ids: list[UUID] = Field(..., description="Associated text UUIDs")
    pending_department_ids: list[UUID] = Field(default_factory=list, description="Pending department UUIDs")
    pending_description_ids: list[UUID] = Field(default_factory=list, description="Pending description UUIDs")
    pending_file_ids: list[UUID] = Field(default_factory=list, description="Pending file UUIDs")
    pending_flag_ids: list[UUID] = Field(default_factory=list, description="Pending flag UUIDs")
    pending_image_ids: list[UUID] = Field(default_factory=list, description="Pending image UUIDs")
    pending_name_ids: list[UUID] = Field(default_factory=list, description="Pending name UUIDs")
    pending_parameter_field_ids: list[UUID] = Field(default_factory=list, description="Pending parameter field UUIDs")
    pending_parameter_ids: list[UUID] = Field(default_factory=list, description="Pending parameter UUIDs")
    pending_text_ids: list[UUID] = Field(default_factory=list, description="Pending text UUIDs")
