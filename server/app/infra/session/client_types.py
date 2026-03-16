"""Client-facing WebSocket types for the Session/Connection domain.

Canonical location for ConnectionConfirmedPayload used between
the client and server over WebSocket / SSE.
"""

from pydantic import BaseModel, Field


class ConnectionConfirmedPayload(BaseModel):
    """Server-to-client: connection confirmed."""

    sid: str = Field(..., description="Socket session identifier")
    profile_id: str | None = Field(..., description="UUID of the user profile")
    guest_id: str | None = Field(..., description="UUID of the guest user")
    server_time: float = Field(..., description="Server timestamp in epoch seconds")
