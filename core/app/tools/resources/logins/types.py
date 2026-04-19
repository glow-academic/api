"""Types for logins resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateLoginsResponse(BaseModel):
    id: UUID


class GetLoginsResponse(BaseModel):
    id: UUID
    profile_id: UUID | None
    auth_id: UUID | None
    icon_id: UUID | None
    display_name: str
    login_type: str
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
