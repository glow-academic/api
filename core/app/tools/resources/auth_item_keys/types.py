"""Types for auth_item_keys resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetAuthItemKeyResponse(BaseModel):
    id: UUID
    auth_id: UUID
    key_id: UUID
    item_id: UUID
    created_at: datetime
    updated_at: datetime
    active: bool
    mcp: bool
    generated: bool
