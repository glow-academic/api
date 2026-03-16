"""Document artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetDocumentsResponse(BaseModel):
    id: UUID = Field(..., description="Unique identifier")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    generated: bool = Field(..., description="Whether document was auto-generated")
    mcp: bool = Field(..., description="Whether document uses MCP")
    active: bool = Field(..., description="Whether document is active")
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = Field(None, description="Associated name junction IDs")
    description_ids: list[UUID] | None = Field(None, description="Associated description junction IDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department junction IDs")
    flag_ids: list[UUID] | None = Field(None, description="Associated flag junction IDs")
    files_ids: list[UUID] | None = Field(None, description="Associated file junction IDs")
    images_ids: list[UUID] | None = Field(None, description="Associated image junction IDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Associated parameter field junction IDs")
    parameter_ids: list[UUID] | None = Field(None, description="Associated parameter junction IDs")
    texts_ids: list[UUID] | None = Field(None, description="Associated text junction IDs")
    document_ids: list[UUID] | None = Field(None, description="Associated document junction IDs")


class CreateDocumentResponse(BaseModel):
    id: UUID = Field(..., description="ID of the created document")


class UpdateDocumentResponse(BaseModel):
    id: UUID = Field(..., description="ID of the updated document")


class DeleteDocumentsResponse(BaseModel):
    deleted_ids: list[UUID] = Field(..., description="UUIDs of deleted documents")
