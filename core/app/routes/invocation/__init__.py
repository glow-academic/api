"""Invocation artifact router."""

from fastapi import APIRouter

from app.routes.invocation.context import router as context_router
from app.routes.invocation.decrypt import router as decrypt_router
from app.routes.invocation.docs import router as docs_router
from app.routes.invocation.draft import router as draft_router
from app.routes.invocation.drafts import router as drafts_router
from app.routes.invocation.export import router as export_router
from app.routes.invocation.generate import router as generate_router
from app.routes.invocation.generations import router as generations_router
from app.routes.invocation.get import router as get_router
from app.routes.invocation.group import router as group_router
from app.routes.invocation.problem import router as problem_router
from app.routes.invocation.refresh import router as refresh_router

router = APIRouter(prefix="/invocation", tags=["invocation"])
router.include_router(get_router)
router.include_router(group_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(problem_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(refresh_router)
router.include_router(export_router)
router.include_router(docs_router)
router.include_router(context_router)
router.include_router(decrypt_router)
