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
    name: str | None = None              # enriched from fields_resource via field_id
    parameter_name: str | None = None    # enriched from parameters_resource via parameter_id
