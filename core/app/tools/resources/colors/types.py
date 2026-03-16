"""Response types for colors resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetColorResponse(BaseModel):
    id: UUID
    name: str
    description: str
    hex_code: str
    type: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
