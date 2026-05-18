"""Types for primary_departments resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetPrimaryDepartmentResponse(BaseModel):
    id: UUID
    departments_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
