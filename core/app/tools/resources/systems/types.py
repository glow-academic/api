"""Systems resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetSystemResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    agent_ids: list[UUID]
    resolution_strategy: str | None
    resolution_threshold: float | None
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
