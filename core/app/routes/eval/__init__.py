"""Eval v4 router."""

from fastapi import APIRouter

from app.routes.eval.context import router as context_router
from app.routes.eval.create import router as create_router
from app.routes.eval.csv import router as csv_router
from app.routes.eval.delete import router as delete_router
from app.routes.eval.draft import router as draft_router
from app.routes.eval.drafts import router as drafts_router
from app.routes.eval.duplicate import router as duplicate_router
from app.routes.eval.export import router as export_router
from app.routes.eval.generate import router as generate_router
from app.routes.eval.generations import router as generations_router
from app.routes.eval.get import router as get_router
from app.routes.eval.group import router as group_router
from app.routes.eval.problem import router as problem_router
from app.routes.eval.refresh import router as refresh_router
from app.routes.eval.search import router as search_router
from app.routes.eval.stream import router as stream_router
from app.routes.eval.update import router as update_router
from app.routes.eval.text import router as text_router
from app.routes.eval.call import router as call_router

router = APIRouter(prefix="/eval", tags=["eval"])

# Standard artifact operations
router.include_router(search_router)
router.include_router(get_router)
router.include_router(create_router)
router.include_router(csv_router)
router.include_router(update_router)
router.include_router(duplicate_router)
router.include_router(delete_router)
router.include_router(draft_router)
router.include_router(drafts_router)
router.include_router(export_router)
router.include_router(generate_router)
router.include_router(generations_router)
router.include_router(context_router)
router.include_router(group_router)
router.include_router(problem_router)
router.include_router(refresh_router)
router.include_router(stream_router)

# Typed media operations
router.include_router(text_router)
router.include_router(call_router)
