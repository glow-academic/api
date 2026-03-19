"""Backup routes — admin-only endpoint to list available DB backups.

GET /backups → List available backups (name, size, timestamp)
"""

from fastapi import APIRouter, Depends, HTTPException

from app.infra.identity.middleware import require_auth
from app.infra.identity.resolve_identity import Identity
from app.services.backups import list_backups

router = APIRouter(prefix="/backups", tags=["backups"])


@router.get("")
async def get_backups(identity: Identity = Depends(require_auth)):
    """List all available backups in the history volume. Admin only."""
    if identity.role not in ("admin", "owner"):
        raise HTTPException(403, "Admin access required")
    return list_backups()
