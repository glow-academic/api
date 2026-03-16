"""Types for profile_personas resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetProfilePersonaResponse(BaseModel):
    id: UUID
    profile_id: UUID
    persona_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
