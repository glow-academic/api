"""Types for permissions resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetPermissionResponse(BaseModel):
    id: UUID
    artifact: str
    operation: str
    name: str
    description: str
    active: bool
    generated: bool
    mcp: bool
    created_at: datetime
