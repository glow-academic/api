"""Types for fields resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetFieldResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the field")
    name: str = Field(..., description="Field name")
    description: str = Field(..., description="Field description")
    value: str = Field(..., description="Field value")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    conditional_parameter_ids: list[UUID] = Field(..., description="Associated conditional parameter UUIDs")
    created_at: datetime = Field(..., description="Creation timestamp")
    active: bool = Field(..., description="Whether the field is active")
    generated: bool = Field(..., description="Whether the field was AI-generated")
    mcp: bool = Field(..., description="Whether the field is from MCP")
