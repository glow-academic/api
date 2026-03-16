"""Args outputs resource types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetArgOutputResponse(BaseModel):
    id: UUID
    args_id: UUID
    name: str
    template: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
