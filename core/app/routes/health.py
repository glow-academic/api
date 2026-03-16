"""Health check endpoint — GET /health."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health_services() -> JSONResponse:
    """Lightweight health check — no DB/Redis/Keycloak connections."""
    return JSONResponse(content={"status": "ok"})
