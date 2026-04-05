"""Route: auto-expire stale attempt chats.

Called by the simulation-expiry sidecar every 60 seconds.
No auth required — internal-only endpoint.
"""

from fastapi import APIRouter

from app.infra.attempt.expire import expire_stale_attempts

router = APIRouter()


@router.post("/expire")
async def expire():
    """Find and end all expired attempt chats."""
    expired = await expire_stale_attempts()
    return {"expired": len(expired), "details": expired}
