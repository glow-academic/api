"""Response types for prompts resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetPromptResponse(BaseModel):
    id: UUID
    system_prompt: str
    name: str
    description: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
