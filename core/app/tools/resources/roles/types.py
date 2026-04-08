"""Types for roles resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetRoleResponse(BaseModel):
    id: UUID
    name: str
    description: str
    icon_id: UUID | None
    color_id: UUID | None
    level: int
    permission_ids: list[UUID]
    request_limit_ids: list[UUID]
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
