"""Provider keys resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetProviderKeyResponse(BaseModel):
    id: UUID
    provider_id: UUID
    key_id: UUID
    key: str
    name: str
    description: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
