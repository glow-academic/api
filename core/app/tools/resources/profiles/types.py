"""Response types for profiles resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetProfileResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    department_ids: list[UUID]
    role_id: UUID | None
    emails: list[str]
    primary_email: str | None
    last_login: datetime
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
