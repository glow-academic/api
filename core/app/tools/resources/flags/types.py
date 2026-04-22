"""Response types for flags resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetFlagResponse(BaseModel):
    id: UUID
    name: str
    description: str
    type: str
    icon_id: UUID | None
    # Hydrated SVG markup (from icons_resource.value) when set by a caller.
    # The bare get_flags tool leaves this None — composite layers (e.g. an
    # artifact context) call `hydrate_flag_icons(...)` to fill it in.
    icon: str | None = None
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
    value: bool
