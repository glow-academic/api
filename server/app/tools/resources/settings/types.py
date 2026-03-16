"""Settings resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetSettingResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    department_ids: list[UUID]
    provider_key_ids: list[UUID]
    auth_ids: list[UUID]
    system_ids: list[UUID]
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
