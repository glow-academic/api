"""Types for parameters resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class GetParameterResponse(BaseModel):
    id: UUID = Field(..., description="UUID of the parameter")
    name: str = Field(..., description="Parameter name")
    description: str = Field(..., description="Parameter description")
    value: str = Field(..., description="Parameter value")
    department_ids: list[UUID] = Field(..., description="Associated department UUIDs")
    persona_parameter: bool = Field(..., description="Whether this is a persona parameter")
    document_parameter: bool = Field(..., description="Whether this is a document parameter")
    scenario_parameter: bool = Field(..., description="Whether this is a scenario parameter")
    video_parameter: bool = Field(..., description="Whether this is a video parameter")
    field_ids: list[UUID] = Field(..., description="Associated field UUIDs")
    created_at: datetime = Field(..., description="Creation timestamp")
    active: bool = Field(..., description="Whether the parameter is active")
    generated: bool = Field(..., description="Whether the parameter was AI-generated")
    mcp: bool = Field(..., description="Whether the parameter is from MCP")
