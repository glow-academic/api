"""Types for roles resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetRoleResponse(BaseModel):
    id: UUID
    role: str
    name: str
    description: str
    icon_id: UUID | None
    color_id: UUID | None
    artifacts: list[str]
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
