"""Types for auth_item_values resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetAuthItemValueResponse(BaseModel):
    id: UUID
    auth_id: UUID
    item_id: UUID
    value: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
