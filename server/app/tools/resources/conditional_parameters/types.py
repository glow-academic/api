"""Types for conditional_parameters resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetConditionalParameterResponse(BaseModel):
    id: UUID
    parameter_id: UUID
    created_at: datetime
    updated_at: datetime
    active: bool
    generated: bool
    mcp: bool
