from fastapi import APIRouter

from app.api.admin.overview import router as overview_router
from app.api.admin.papers import router as papers_router
from app.api.admin.canonical_documents import router as canonical_documents_router
from app.api.admin.activity import router as admin_activity_router
router = APIRouter(prefix="/admin", tags=["admin"])

router.include_router(overview_router)
router.include_router(papers_router)
router.include_router(canonical_documents_router)
router.include_router(admin_activity_router)