"""Keys resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetKeyResponse(BaseModel):
    id: UUID
    key: str
    name: str
    description: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
