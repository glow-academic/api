"""Args resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetArgResponse(BaseModel):
    id: UUID
    name: str
    description: str
    field_type: str
    required: bool
    default_value: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
