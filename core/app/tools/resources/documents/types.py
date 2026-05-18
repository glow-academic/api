"""Types for documents resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetDocumentResponse(BaseModel):
    id: UUID
    name: str
    description: str
    department_ids: list[UUID]
    file_id: UUID | None
    text_id: UUID | None
    image_ids: list[UUID]
    template: bool
    parameter_field_ids: list[UUID]
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
