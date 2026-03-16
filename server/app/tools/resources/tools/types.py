"""Tools resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetToolResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    operation: str | None
    department_ids: list[UUID]
    args_ids: list[UUID]
    args_output_ids: list[UUID]
    artifacts: list[str]
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
