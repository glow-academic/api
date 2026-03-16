"""Types for artifacts resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetArtifactResponse(BaseModel):
    id: UUID
    artifact: str
    active: bool
    generated: bool
    mcp: bool
    created_at: datetime
