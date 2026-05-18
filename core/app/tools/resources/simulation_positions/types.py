"""Types for simulation_positions resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetSimulationPositionResponse(BaseModel):
    id: UUID
    simulation_id: UUID
    value: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
