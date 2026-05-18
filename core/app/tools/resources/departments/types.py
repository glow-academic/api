"""Departments resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetDepartmentResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    department_ids: list[UUID]
    setting_ids: list[UUID]
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
