from fastapi import APIRouter
from app.api.papers import router as papers_router

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok"}

router.include_router(papers_router)