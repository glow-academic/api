"""Test run sub-router — POST /test/run + POST /test/run/end."""

from fastapi import APIRouter

from app.routes.test.run.create import router as create_router
from app.routes.test.run.end import router as end_router

router = APIRouter(prefix="/run", tags=["test-run"])
router.include_router(create_router)
router.include_router(end_router)
