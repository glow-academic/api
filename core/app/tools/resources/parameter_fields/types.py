"""Types for parameter fields resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetParameterFieldResponse(BaseModel):
    id: UUID
    field_id: UUID
    parameter_id: UUID | None
    created_at: datetime
    updated_at: datetime
    active: bool
    generated: bool
    mcp: bool
