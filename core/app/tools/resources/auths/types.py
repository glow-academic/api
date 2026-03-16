"""Auths resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetAuthResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    department_ids: list[UUID]
    slug: str | None
    protocol: str | None
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
